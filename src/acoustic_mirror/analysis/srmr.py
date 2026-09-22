"""SRMR (Speech-to-Reverberation Modulation Energy Ratio) computation.

Implements the SRMR metric without external dependencies (no SRMRpy).
Pipeline: gammatone filterbank → Hilbert envelope → modulation spectrum → ratio.

This is a SIMPLIFIED implementation inspired by Falk et al. (2010), "A
Non-Intrusive Quality and Intelligibility Measure of Reverberant and
Dereverberated Speech" — it does NOT reproduce the reference algorithm
exactly, and its absolute values do NOT match SRMRpy or other reference
implementations. Known simplifications (see docs/adr/ADR-0001):
  - The low/high modulation band split (K*) is fixed at 4 of 8 bands,
    rather than the original's signal-adaptive K*.
  - The modulation filterbank is a rectangular FFT-bin mask over 8 fixed
    bands (4-100 Hz), not a true Q=2 modulation filterbank.
Thresholds derived from other SRMR implementations or the literature do
NOT transfer to this implementation; see RoomType.srmr_target for the
values calibrated against this implementation's own output distribution.

Reference: Falk et al. (2010), "A Non-Intrusive Quality and Intelligibility
Measure of Reverberant and Dereverberated Speech"
"""

from dataclasses import dataclass

import numpy as np
from scipy.signal import decimate, gammatone, hilbert

_ENERGY_FLOOR = 1e-10


def _erb_space(low_freq: float, high_freq: float, n: int) -> np.ndarray:
    """Compute n center frequencies equally spaced on the ERB scale."""
    ear_q = 9.26449
    min_bw = 24.7
    low_erb = ear_q * np.log(1 + low_freq / (ear_q * min_bw))
    high_erb = ear_q * np.log(1 + high_freq / (ear_q * min_bw))
    erb_points = np.linspace(low_erb, high_erb, n)
    return (ear_q * min_bw) * (np.exp(erb_points / ear_q) - 1)


@dataclass
class SRMRResult:
    srmr_score: float
    energy: np.ndarray  # (n_channels, n_mod_bands)
    is_valid: bool


def _apply_fir(b: np.ndarray, signal: np.ndarray) -> np.ndarray:
    """Apply FIR filter using numpy convolution, output same length as input."""
    from numpy import convolve

    out = convolve(signal, b, mode="full")[: len(signal)]
    return out


class GammatoneFilterbank:
    """Bank of gammatone bandpass filters on the ERB scale."""

    def __init__(
        self,
        n_filters: int = 23,
        low_freq: float = 125.0,
        high_freq: float = 7500.0,
        sample_rate: int = 16000,
    ) -> None:
        self._n_filters = n_filters
        self._sample_rate = sample_rate
        self._center_freqs = _erb_space(low_freq, high_freq, n_filters)

        # Clamp center frequencies below Nyquist
        nyquist = sample_rate / 2.0
        self._center_freqs = np.minimum(self._center_freqs, nyquist * 0.95)

        # Pre-compute FIR coefficients for each channel
        self._fir_coeffs = []
        for cf in self._center_freqs:
            b, _ = gammatone(cf, ftype="fir", order=4, numtaps=129, fs=sample_rate)
            self._fir_coeffs.append(b)

    @property
    def n_filters(self) -> int:
        return self._n_filters

    @property
    def center_frequencies(self) -> np.ndarray:
        return self._center_freqs.copy()

    def apply(self, signal: np.ndarray) -> np.ndarray:
        """Apply all filters to the signal. Returns (n_filters, n_samples)."""
        sig = signal.astype(np.float64)
        output = np.empty((self._n_filters, len(signal)), dtype=np.float64)
        for i, b in enumerate(self._fir_coeffs):
            output[i] = _apply_fir(b, sig)
        return output


def _modulation_filterbank_centers(n_bands: int = 8) -> np.ndarray:
    """Log-spaced modulation band center frequencies, 4-100 Hz.

    This is a simplified approximation of Falk et al. (2010)'s modulation
    filterbank (see module docstring): 8 fixed bands with a rectangular
    (FFT-bin-mask) split rather than a true Q=2 filterbank, and a fixed
    K*=4/8 split between low/high modulation energy rather than the
    signal-adaptive K* of the original method. These are accepted
    simplifications, not bugs (see docs/adr/ADR-0001) — they are kept
    because they don't lose information, only approximate the reference
    filter shapes.
    """
    return np.array([4.0, 6.3, 10.0, 16.0, 25.2, 40.0, 63.5, 100.0])[:n_bands]


def compute_modulation_energy(
    envelopes: np.ndarray,
    sample_rate: int,
    n_mod_bands: int = 8,
) -> np.ndarray:
    """Compute modulation spectrum energy for each cochlear channel.

    Args:
        envelopes: (n_channels, n_samples) Hilbert envelopes
        sample_rate: of the original audio (envelopes are at same rate)
        n_mod_bands: number of modulation frequency bands

    Returns:
        energy: (n_channels, n_mod_bands) modulation energy matrix
    """
    n_channels, n_samples = envelopes.shape
    mod_centers = _modulation_filterbank_centers(n_mod_bands)

    # Downsample to ~400 Hz for efficiency. scipy.signal.decimate applies an
    # anti-aliasing lowpass before downsampling (unlike naive striding, which
    # folds envelope content above the new Nyquist back into the modulation
    # bands — see docs/adr/ADR-0001, issue #4).
    downsample_factor = max(1, sample_rate // 400)
    if downsample_factor > 1:
        env_ds = decimate(envelopes, downsample_factor, ftype="fir", zero_phase=True, axis=1)
    else:
        env_ds = envelopes.astype(np.float64)
    ds_rate = sample_rate / downsample_factor
    n_fft = env_ds.shape[1]

    if n_fft < 4:
        return np.zeros((n_channels, n_mod_bands), dtype=np.float64)

    # Remove DC per channel
    env_ds = env_ds - np.mean(env_ds, axis=1, keepdims=True)

    # Hann window before FFT to limit spectral leakage from the strong
    # low-modulation energy in speech envelopes into the high-modulation
    # (denominator) bands — see docs/adr/ADR-0001, issue #5.
    window = np.hanning(n_fft)
    spectrum = np.abs(np.fft.rfft(env_ds * window, axis=1)) ** 2
    freqs = np.fft.rfftfreq(n_fft, d=1.0 / ds_rate)

    energy = np.zeros((n_channels, n_mod_bands), dtype=np.float64)
    for b in range(n_mod_bands):
        cf = mod_centers[b]
        # Bandwidth = center_freq / Q, with Q = 2
        bw = cf / 2.0
        low = cf - bw / 2
        high = cf + bw / 2
        mask = (freqs >= low) & (freqs < high)
        energy[:, b] = np.sum(spectrum[:, mask], axis=1)

    return energy


class SRMRProcessor:
    """Compute SRMR for audio chunks."""

    def __init__(
        self,
        sample_rate: int = 16000,
        n_cochlear_filters: int = 23,
        n_mod_bands: int = 8,
    ) -> None:
        self._sample_rate = sample_rate
        self._n_mod_bands = n_mod_bands
        self._filterbank = GammatoneFilterbank(
            n_filters=n_cochlear_filters, sample_rate=sample_rate
        )

    def process(self, chunk: np.ndarray, is_speech: bool) -> SRMRResult:
        """Compute SRMR for a single audio chunk.

        Args:
            chunk: audio samples (typically 500ms = 8000 samples at 16kHz)
            is_speech: whether speech is detected in this chunk

        Returns:
            SRMRResult with score, energy matrix, and validity flag
        """
        empty_energy = np.zeros(
            (self._filterbank.n_filters, self._n_mod_bands), dtype=np.float64
        )

        if not is_speech:
            return SRMRResult(srmr_score=0.0, energy=empty_energy, is_valid=False)

        # Step 1: Gammatone filterbank
        filtered = self._filterbank.apply(chunk)  # (n_channels, n_samples)

        # Step 2: Hilbert envelope
        envelopes = np.abs(hilbert(filtered, axis=1))

        # Step 3-5: Modulation spectrum energy
        energy = compute_modulation_energy(
            envelopes, self._sample_rate, self._n_mod_bands
        )

        # Step 6: SRMR = sum of low-mod energy / sum of high-mod energy
        # Low modulation bands (1-4): indices 0-3, carrying speech info
        # High modulation bands (5-8): indices 4-7, reverb smearing
        low_energy = np.sum(energy[:, :4])
        high_energy = np.sum(energy[:, 4:])

        if high_energy < _ENERGY_FLOOR:
            srmr = 0.0 if low_energy < _ENERGY_FLOOR else 100.0
        else:
            srmr = float(low_energy / high_energy)

        return SRMRResult(srmr_score=srmr, energy=energy, is_valid=True)
