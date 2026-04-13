"""Haptic vibration pattern definitions for Pixel Watch.

Each cause of intelligibility loss maps to a distinct vibration pattern
designed to intuitively suggest the corrective action. Phase 1 stores
these as data only (no device integration).
"""

from dataclasses import dataclass


@dataclass
class HapticPattern:
    name: str
    cause: str
    sequence: list[tuple[float, int]]  # (intensity 0–1, duration_ms)
    description: str

    @property
    def duration_ms(self) -> int:
        return sum(d for _, d in self.sequence)

    def to_dict(self) -> dict:
        return {
            "name": self.name,
            "cause": self.cause,
            "sequence": [{"intensity": i, "duration_ms": d} for i, d in self.sequence],
            "duration_ms": self.duration_ms,
            "description": self.description,
        }

    def bar_chart_data(self) -> list[dict]:
        bars = []
        offset = 0
        for intensity, duration in self.sequence:
            bars.append({
                "intensity": intensity,
                "duration_ms": duration,
                "offset_ms": offset,
            })
            offset += duration
        return bars


# Pattern definitions from the design document
PATTERNS: dict[str, HapticPattern] = {
    "reverb": HapticPattern(
        name="slow_pulse",
        cause="reverb",
        sequence=[
            (0.8, 300),  # ON
            (0.0, 500),  # OFF
            (0.8, 300),  # ON
            (0.0, 500),  # OFF
        ],
        description="ゆったりしたリズム → 「ゆっくり」を体で誘導",
    ),
    "noise": HapticPattern(
        name="rapid_tap",
        cause="noise",
        sequence=[
            (1.0, 50), (0.0, 50),
            (1.0, 50), (0.0, 50),
            (1.0, 50), (0.0, 50),
            (1.0, 50), (0.0, 50),
            (1.0, 50), (0.0, 50),
        ],
        description="速い連打 → 緊急性、「もっとエネルギーを」",
    ),
    "articulation": HapticPattern(
        name="double_tap",
        cause="articulation",
        sequence=[
            (0.9, 80),   # tap 1
            (0.0, 120),  # pause
            (0.9, 80),   # tap 2
            (0.0, 400),  # long pause
        ],
        description="2回タップ → 「はっきり、くっきり」",
    ),
    "distance": HapticPattern(
        name="rising_pulse",
        cause="distance",
        sequence=[
            (0.3, 50),
            (0.5, 100),
            (0.7, 150),
            (1.0, 200),
        ],
        description="だんだん強くなる → 「近づいてくる」イメージ",
    ),
}


def get_pattern(cause: str) -> HapticPattern:
    """Get the haptic pattern for a given cause. Raises KeyError if unknown."""
    return PATTERNS[cause]
