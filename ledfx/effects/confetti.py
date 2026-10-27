from typing import ClassVar, Literal

import numpy as np
from pydantic import Field
from typing_extensions import override

from ledfx.configuration.fields import CoercedFloat, CoercedInt
from ledfx.configuration.plugin import TypedConfig
from ledfx.effects.audio import AudioAnalysisSource, AudioReactiveEffect
from ledfx.effects.gradient import GradientEffect
from ledfx.effects.utils.custom import (
    CUSTOM_CATEGORY,
    BeatLatch,
    FloatArray,
    frame_step,
)

# A beat throws this many times more confetti than a plain percussive hit
BEAT_BURST = 2

ConfettiTrigger = Literal["Percussion", "Beat", "Both"]


class Confetti(AudioReactiveEffect, GradientEffect):
    NAME = "Confetti"
    CATEGORY = CUSTOM_CATEGORY
    # Effect declares HIDDEN_KEYS = None, so every list override trips bad-override.
    HIDDEN_KEYS: ClassVar[list[str]] = ["gradient_roll"]  # pyrefly: ignore[bad-override]

    class Config(GradientEffect.Config):
        sparkles_per_hit: CoercedInt = Field(
            8, description="How many sparkles each hit throws", ge=1, le=30
        )
        spread: CoercedFloat = Field(
            0.3,
            description="How widely a burst scatters, as a share of the strip",
            ge=0.05,
            le=1.0,
        )
        fade: CoercedFloat = Field(
            4.0,
            description="How fast sparkles fade. Higher -> shorter",
            ge=1.0,
            le=15.0,
        )
        twinkle: bool = Field(True, description="Sparkles flicker while they fade")
        trigger: ConfettiTrigger = Field(
            "Both",
            description="Throw confetti on percussive hits, on the beat, or both (beats throw more)",
        )

    config = TypedConfig(Config)

    def on_activate(self, pixel_count: int) -> None:
        self._level: FloatArray = np.zeros(pixel_count)
        self._colors: FloatArray = np.zeros((pixel_count, 3))
        self._hits = BeatLatch()
        self._beats = BeatLatch()

    @override
    def config_updated(self, config: object) -> None:
        if not hasattr(self, "_rng"):
            self._rng = np.random.default_rng()

    @override
    def audio_data_updated(self, data: AudioAnalysisSource) -> None:
        trigger = self.config.trigger
        if trigger != "Beat":
            self._hits.listen(data, "Percussion")
        if trigger != "Percussion":
            self._beats.listen(data, "Beat")

    def _burst(self, count: int) -> None:
        n = self.pixel_count
        center = self._rng.uniform(0, n)
        offsets = self._rng.normal(0, self.config.spread * n / 2, count)
        spots = np.clip((center + offsets).astype(int), 0, n - 1)
        self._level[spots] = 1.0
        self._colors[spots] = self.get_gradient_color_vectorized1d(
            self._rng.random(count)
        )

    @override
    def render(self) -> None:
        dt = frame_step(self.passed)
        self._level *= float(np.exp(-dt * self.config.fade))
        per_hit = self.config.sparkles_per_hit
        if self._hits.take(self.now):
            self._burst(per_hit)
        if self._beats.take(self.now):
            self._burst(per_hit * BEAT_BURST)

        level = self._level
        if self.config.twinkle:
            level = level * self._rng.uniform(0.5, 1.0, level.size)
        self.pixels = self._colors * level[:, None]
