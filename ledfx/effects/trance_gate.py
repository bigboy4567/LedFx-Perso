from typing import ClassVar, Literal

import numpy as np
from pydantic import Field
from typing_extensions import override

from ledfx.configuration.fields import CoercedFloat
from ledfx.configuration.plugin import TypedConfig
from ledfx.effects.audio import AudioAnalysisSource, AudioReactiveEffect
from ledfx.effects.gradient import GradientEffect
from ledfx.effects.utils.custom import (
    CUSTOM_CATEGORY,
    BoolArray,
    FloatArray,
    TempoTracker,
)

# A bar of sixteenth notes; 1 lets the light through, 0 cuts it
STEPS = 16
PATTERNS = {
    "Classic": "1011101010111010",
    "Offbeat": "0010001000100010",
    "Triplet": "1101101101101101",
    "Stutter": "1111000011001010",
}
# Share of the steps that open in a random pattern
RANDOM_DENSITY = 0.6

Pattern = Literal["Classic", "Offbeat", "Triplet", "Stutter", "Random"]


def gate_steps(pattern: str) -> BoolArray:
    return np.array([step == "1" for step in pattern], dtype=bool)


class TranceGate(AudioReactiveEffect, GradientEffect):
    NAME = "Trance Gate"
    CATEGORY = CUSTOM_CATEGORY
    # Effect declares HIDDEN_KEYS = None, so every list override trips bad-override.
    HIDDEN_KEYS: ClassVar[list[str]] = ["gradient_roll"]  # pyrefly: ignore[bad-override]

    class Config(GradientEffect.Config):
        pattern: Pattern = Field(
            "Classic",
            description="Which sixteenth notes of the bar let the light through; Random draws a new one each bar",
        )
        depth: CoercedFloat = Field(
            1.0, description="How dark the gate goes when closed", ge=0.3, le=1.0
        )
        smoothness: CoercedFloat = Field(
            0.15,
            description="How softly the gate opens and closes, as a share of a step",
            ge=0.0,
            le=0.5,
        )

    config = TypedConfig(Config)

    def on_activate(self, pixel_count: int) -> None:
        self._u: FloatArray = np.arange(pixel_count) / max(pixel_count - 1, 1)
        self._bar = -1
        self._random: BoolArray = np.ones(STEPS, dtype=bool)
        self._tempo = TempoTracker()

    @override
    def config_updated(self, config: object) -> None:
        if not hasattr(self, "_rng"):
            self._rng = np.random.default_rng()

    @override
    def audio_data_updated(self, data: AudioAnalysisSource) -> None:
        self._tempo.listen(data)

    def steps(self) -> BoolArray:
        if self.config.pattern != "Random":
            return gate_steps(PATTERNS[self.config.pattern])
        bar = int(self._tempo.beats // 4)
        if bar != self._bar:
            self._bar = bar
            self._random = self._rng.random(STEPS) < RANDOM_DENSITY
            self._random[0] = True
        return self._random

    def gate(self) -> float:
        """How open the gate is right now, 0 to 1."""
        steps = self.steps()
        position = self._tempo.beats * 4
        index = int(position) % STEPS
        within = position % 1
        if not steps[index]:
            return 0.0
        soft = self.config.smoothness / 2 + 1e-3
        opening = min(1.0, within / soft) if not steps[index - 1] else 1.0
        # Open steps run on into each other; a step before a closed one shuts early
        closing = (
            min(1.0, (1 - within) / soft) if not steps[(index + 1) % STEPS] else 1.0
        )
        return min(opening, closing)

    @override
    def render(self) -> None:
        level = 1 - self.config.depth * (1 - self.gate())
        drift = self._tempo.beats / STEPS
        colors = self.get_gradient_color_vectorized1d((self._u * 0.5 + drift) % 1)
        self.pixels = colors * level
