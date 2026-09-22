"""ADR-0005 V7: what the rolling RT60 estimator costs per 500ms chunk.

The estimator runs find_decay_events over the whole 3s window on every
chunk, which is the obvious objection to the design. This measures it
against the 500ms budget the streaming loop actually has.

    .venv/bin/python benchmarks/streaming-rt60/run.py
"""

import statistics
import sys
import time
from pathlib import Path

import numpy as np

sys.path.insert(0, str(Path(__file__).resolve().parents[2]))
sys.path.insert(0, str(Path(__file__).resolve().parents[2] / "src"))

from acoustic_mirror.analysis.rolling_rt60 import RollingRT60Estimator  # noqa: E402
from tests.synth import reverberant_utterances  # noqa: E402

SR = 16000
CHUNK = SR // 2
WINDOW = 3 * SR
BUDGET_MS = 500.0


def measure(rt60: float, gap: float, repeats: int = 5) -> list[float]:
    clip = reverberant_utterances(rt60, gap=gap, seed=1)
    per_chunk = []
    for _ in range(repeats):
        est = RollingRT60Estimator(sample_rate=SR)
        for end in range(CHUNK, len(clip) + 1, CHUNK):
            start = max(0, end - WINDOW)
            if end - start < WINDOW:
                continue
            window = clip[start:end].astype(np.float32)
            t0 = time.perf_counter()
            est.push(window, window_start=start)
            per_chunk.append((time.perf_counter() - t0) * 1000)
    return per_chunk


def main() -> None:
    print(f"{'RT60':>5} {'gap':>5} | {'mean ms':>8} {'p95 ms':>8} {'max ms':>8} {'% of 500ms':>11}")
    worst = 0.0
    for gap in (0.7, 1.2):
        for rt60 in (0.3, 0.6, 1.0):
            samples = measure(rt60, gap)
            mean = statistics.mean(samples)
            p95 = sorted(samples)[int(len(samples) * 0.95)]
            mx = max(samples)
            worst = max(worst, mx)
            print(f"{rt60:>5.1f} {gap:>5.1f} | {mean:>8.2f} {p95:>8.2f} {mx:>8.2f} {mx / BUDGET_MS * 100:>10.2f}%")
    print(f"\nworst case {worst:.2f}ms of a {BUDGET_MS:.0f}ms chunk "
          f"({worst / BUDGET_MS * 100:.2f}%)")


if __name__ == "__main__":
    main()
