"""Diagnose the primary cause of intelligibility loss.

When SRMR falls below the room's target, this module identifies whether the
dominant cause is reverberation, background noise, poor articulation, or
excessive distance, and returns a cause-specific action recommendation.
"""

from dataclasses import dataclass

import numpy as np

from acoustic_mirror.analysis.room_profiler import RoomProfile

_ACTIONS = {
    "reverb": "ゆっくり話してください",
    "noise": "声を大きくしてください",
    "articulation": "はっきり発音してください",
    "distance": "相手に近づいてください",
}


@dataclass
class CauseResult:
    primary_cause: str | None
    severity: float  # 0.0–1.0, overall severity of intelligibility loss
    action: str
    scores: dict[str, float]


class CauseSeparator:
    """Rule-based cause diagnosis for intelligibility loss."""

    def diagnose(
        self,
        srmr_score: float,
        srmr_target: float,
        room_profile: RoomProfile,
    ) -> CauseResult:
        empty_scores = {"reverb": 0.0, "noise": 0.0, "articulation": 0.0, "distance": 0.0}

        if srmr_score >= srmr_target:
            return CauseResult(
                primary_cause=None, severity=0.0, action="", scores=empty_scores
            )

        # Overall severity: how far below target
        severity = float(np.clip((srmr_target - srmr_score) / srmr_target, 0, 1))

        # Score each potential cause (0–1 range)
        # Reverb: ramps from RT60=0.3s to 1.0s
        reverb_score = float(np.clip((room_profile.rt60 - 0.3) / 0.7, 0, 1))

        # Noise: ramps from -50dBFS to -30dBFS
        noise_score = float(np.clip((room_profile.noise_floor_db + 50) / 20, 0, 1))

        # Distance: ramps from early-to-late ratio=5dB down to -5dB
        distance_score = float(np.clip((5 - room_profile.early_to_late_ratio_db) / 10, 0, 1))

        # Articulation: residual — high when other scores are low
        max_env = max(reverb_score, noise_score, distance_score)
        articulation_score = float(np.clip(severity * (1 - max_env), 0, 1))

        scores = {
            "reverb": reverb_score,
            "noise": noise_score,
            "articulation": articulation_score,
            "distance": distance_score,
        }

        # Primary cause is the highest-scoring
        primary = max(scores, key=scores.get)  # type: ignore[arg-type]
        action = _ACTIONS[primary]

        return CauseResult(
            primary_cause=primary,
            severity=severity,
            action=action,
            scores=scores,
        )
