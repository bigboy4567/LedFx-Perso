from typing import ClassVar

import numpy as np
from pydantic import Field
from typing_extensions import override

from ledfx.configuration.fields import CoercedFloat, Color
from ledfx.configuration.plugin import TypedConfig
from ledfx.effects.audio import AudioAnalysisSource, AudioReactiveEffect
from ledfx.effects.gradient import GradientEffect
from ledfx.effects.utils.custom import (
    AUDIO_STEP,
    CUSTOM_CATEGORY,
    FloatArray,
    color_array,
    frame_step,
    volume_of,
)

# The recent peak fades this fast, per second, so quiet songs still thaw it
PEAK_FADE = 0.15
# Frost grows this ragged at its edge, as a share of the strip
RAGGED = 0.03
# Ice melts this many times faster than it forms
MELT = 3.0


class Freeze(AudioReactiveEffect, GradientEffect):
    NAME = "Freeze"
    CATEGORY = CUSTOM_CATEGORY
    # Effect declares HIDDEN_KEYS = None, so every list override trips bad-override.
    HIDDEN_KEYS: ClassVar[list[str]] = ["gradient_roll"]  # pyrefly: ignore[bad-override]

    class Config(GradientEffect.Config):
        frost_color: Color = Field("#CDEBFF", description="Color of the frost")
        quiet: CoercedFloat = Field(
            0.35,
            description="How quiet the music must be, against its recent peak, for frost to form",
            ge=0.05,
            le=0.9,
        )
        speed: CoercedFloat = Field(
            0.2,
            description="How fast the frost creeps in, in strips per second",
            ge=0.02,
            le=1.0,
        )

    config = TypedConfig(Config)

    def on_activate(self, pixel_count: int) -> None:
        self._u: FloatArray = np.arange(pixel_count) / max(pixel_count - 1, 1)
        self._edge: FloatArray = np.minimum(self._u, 1 - self._u) + self._rng.uniform(
            0, RAGGED, pixel_count
        )
        # How far the frost has crept in from each end, up to the middle
        self.frost = 0.0
        self._volume = 0.0
        self._peak = 0.0

    @override
    def config_updated(self, config: object) -> None:
        if not hasattr(self, "_rng"):
            self._rng = np.random.default_rng()
        self._frost = color_array(self.config.frost_color)

    @override
    def audio_data_updated(self, data: AudioAnalysisSource) -> None:
        self._volume += (volume_of(data) - self._volume) * 0.1
        self._peak = max(
            self._volume, self._peak * float(np.exp(-AUDIO_STEP * PEAK_FADE))
        )

    @override
    def render(self) -> None:
        dt = frame_step(self.passed)
        quiet = self._volume < self.config.quiet * self._peak or self._peak < 0.02
        step = dt * self.config.speed
        self.frost = float(
            np.clip(self.frost + (step if quiet else -step * MELT), 0, 0.5 + RAGGED)
        )

        frozen = self._edge < self.frost
        thawed = self.get_gradient_color_vectorized1d(self._u) * (
            0.25 + 0.75 * min(1.0, self._volume * 2)
        )
        # Ice crystals catch the light here and there
        sparkle = 0.35 + 0.65 * (self._rng.random(self.pixel_count) < 0.04)
        self.pixels = np.where(frozen[:, None], self._frost * sparkle[:, None], thawed)
