from typing import ClassVar

import numpy as np
from pydantic import Field
from typing_extensions import override

from ledfx.configuration.fields import CoercedFloat
from ledfx.configuration.plugin import TypedConfig
from ledfx.effects.audio import AudioAnalysisSource, AudioReactiveEffect
from ledfx.effects.gradient import GradientEffect
from ledfx.effects.utils.corsair import CORSAIR_CATEGORY, mat_layout
from ledfx.effects.utils.custom import (
    BeatLatch,
    FloatArray,
    Trigger,
    frame_step,
)

# Splashes running at once, at most; the oldest makes room
MAX_SPLASHES = 4
# The pad's edge glows faintly with a slowly turning gradient between splashes
IDLE = 0.12


class MatSplash(AudioReactiveEffect, GradientEffect):
    NAME = "Mat Splash"
    CATEGORY = CORSAIR_CATEGORY
    # Effect declares HIDDEN_KEYS = None, so every list override trips bad-override.
    HIDDEN_KEYS: ClassVar[list[str]] = ["gradient_roll"]  # pyrefly: ignore[bad-override]

    class Config(GradientEffect.Config):
        speed: CoercedFloat = Field(
            1.5,
            description="How fast a splash climbs the sides of the pad, in edges per second",
            ge=0.3,
            le=6.0,
        )
        trigger: Trigger = Field(
            "Beat", description="Splash on the bass or on every percussive hit"
        )

    config = TypedConfig(Config)

    def on_activate(self, pixel_count: int) -> None:
        mat = mat_layout(pixel_count)
        self._along: FloatArray = mat.along
        self._mouse = mat.mouse
        # How far each LED is from the middle of the bottom edge, 0 to 1 at the tips of the U
        self._from_middle: FloatArray = np.abs(mat.along - 0.5) * 2
        self._ages: FloatArray = np.full(MAX_SPLASHES, np.inf)
        self._hues: FloatArray = np.zeros(MAX_SPLASHES)
        self._hue = 0.0
        self._turn = 0.0
        self._latch = BeatLatch()

    @override
    def audio_data_updated(self, data: AudioAnalysisSource) -> None:
        self._latch.listen(data, self.config.trigger)

    @override
    def render(self) -> None:
        dt = frame_step(self.passed)
        self._ages += dt
        self._turn = (self._turn + dt * 0.05) % 1
        if self._latch.take(self.now):
            slot = int(np.argmax(self._ages))
            self._ages[slot] = 0.0
            self._hue = (self._hue + 0.17) % 1
            self._hues[slot] = self._hue

        pixels = (
            self.get_gradient_color_vectorized1d((self._along + self._turn) % 1) * IDLE
        )
        colors = self.get_gradient_color_vectorized1d(self._hues)
        newest = int(np.argmin(self._ages))
        for age, color in zip(self._ages, colors, strict=True):
            front = age * self.config.speed
            if front > 1.5:
                continue
            # From the middle of the bottom edge, the splash runs up both sides at once
            behind = front - self._from_middle
            level = np.where(
                behind >= 0, np.exp(-behind * 4), np.exp(behind * 20)
            ) * max(0.0, 1 - front / 1.5)
            np.maximum(pixels, color * level[:, None], out=pixels)
        # The mouse shows the color of the latest splash, fading with it
        if self._mouse.any():
            fade = (
                max(0.1, 1 - self._ages[newest] * 2)
                if np.isfinite(self._ages[newest])
                else 0.1
            )
            pixels[self._mouse] = colors[newest] * fade
        self.pixels = np.clip(pixels, 0, 255)
