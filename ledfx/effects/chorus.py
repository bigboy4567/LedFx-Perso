from typing import ClassVar

import numpy as np
from pydantic import Field
from typing_extensions import override

from ledfx.configuration.fields import CoercedFloat, CoercedInt
from ledfx.configuration.plugin import TypedConfig
from ledfx.effects.audio import AudioAnalysisSource, AudioReactiveEffect
from ledfx.effects.gradient import GradientEffect
from ledfx.effects.utils.custom import (
    CUSTOM_CATEGORY,
    FloatArray,
    frame_step,
)

# Bands of light in each voice, and how fast the voices' LFOs differ from each other
BANDS = 6
RATE_SPREAD = 0.27
# Each voice is tinted a little further along the gradient than the one before
TINT_STEP = 0.04


class Chorus(AudioReactiveEffect, GradientEffect):
    NAME = "Chorus"
    CATEGORY = CUSTOM_CATEGORY
    # Effect declares HIDDEN_KEYS = None, so every list override trips bad-override.
    HIDDEN_KEYS: ClassVar[list[str]] = ["gradient_roll"]  # pyrefly: ignore[bad-override]

    class Config(GradientEffect.Config):
        voices: CoercedInt = Field(3, description="Copies of the pattern", ge=1, le=5)
        detune: CoercedFloat = Field(
            0.05,
            description="How far the copies drift apart, as a share of the strip",
            ge=0.0,
            le=0.2,
        )
        rate: CoercedFloat = Field(
            0.6,
            description="How fast the copies sway, in sways per second",
            ge=0.05,
            le=3.0,
        )

    config = TypedConfig(Config)

    def on_activate(self, pixel_count: int) -> None:
        self._u: FloatArray = np.arange(pixel_count) / max(pixel_count - 1, 1)
        self._time = 0.0
        self._mids = 0.0

    @override
    def audio_data_updated(self, data: AudioAnalysisSource) -> None:
        self._mids = float(data.mids_power())

    def voice(self, index: int) -> FloatArray:
        # A slightly detuned copy: it sways back and forth at its own pace
        depth = self.config.detune * (0.5 + self._mids)
        rate = self.config.rate * (1 + RATE_SPREAD * index)
        offset = depth * float(np.sin(2 * np.pi * rate * self._time + index))
        u = self._u + offset
        bands = 0.5 + 0.5 * np.cos(2 * np.pi * (u * BANDS - self._time * 0.2))
        colors = self.get_gradient_color_vectorized1d((u + index * TINT_STEP) % 1)
        return colors * (0.15 + 0.85 * bands**2)[:, None]

    @override
    def render(self) -> None:
        self._time += frame_step(self.passed)
        voices = self.config.voices
        self.pixels = np.mean([self.voice(index) for index in range(voices)], axis=0)
