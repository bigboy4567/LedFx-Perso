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
    volume_of,
)

# Driven past this, a wave clips and glows white-hot
CLIP = 2.5
WHITE = np.array((255.0, 255.0, 255.0))


class Overdrive(AudioReactiveEffect, GradientEffect):
    NAME = "Overdrive"
    CATEGORY = CUSTOM_CATEGORY
    # Effect declares HIDDEN_KEYS = None, so every list override trips bad-override.
    HIDDEN_KEYS: ClassVar[list[str]] = ["gradient_roll"]  # pyrefly: ignore[bad-override]

    class Config(GradientEffect.Config):
        gain: CoercedFloat = Field(
            6.0, description="How hard loud music drives the waves", ge=1.0, le=20.0
        )
        waves: CoercedInt = Field(3, description="Waves along the strip", ge=1, le=12)
        clip_glow: bool = Field(True, description="Clipped peaks glow white-hot")

    config = TypedConfig(Config)

    def on_activate(self, pixel_count: int) -> None:
        self._u: FloatArray = np.arange(pixel_count) / max(pixel_count - 1, 1)
        self._time = 0.0
        self._volume = 0.0

    @override
    def audio_data_updated(self, data: AudioAnalysisSource) -> None:
        self._volume = volume_of(data)

    def drive(self) -> float:
        return 1 + self.config.gain * min(1.0, self._volume * 2)

    @override
    def render(self) -> None:
        self._time += frame_step(self.passed)
        u, t, waves = self._u, self._time, self.config.waves
        wave = np.sin(2 * np.pi * (u * waves - t * 0.3)) + 0.5 * np.sin(
            2 * np.pi * (u * waves * 2.1 + t * 0.5)
        )
        # Soft clipping: gentle waves pass through, driven ones flatten into hard bands
        drive = self.drive()
        shaped = np.tanh(drive * wave) / np.tanh(drive)
        level = 0.5 + 0.5 * shaped
        pixels = (
            self.get_gradient_color_vectorized1d(np.clip(level, 0, 1)) * level[:, None]
        )
        if self.config.clip_glow:
            hot = np.clip((np.abs(drive * wave) - CLIP) / CLIP, 0, 1)[:, None] * 0.6
            pixels = pixels + (WHITE - pixels) * hot
        self.pixels = np.clip(pixels, 0, 255)
