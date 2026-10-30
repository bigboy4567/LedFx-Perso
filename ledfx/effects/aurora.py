from typing import ClassVar

import numpy as np
from pydantic import Field
from typing_extensions import override

from ledfx.configuration.fields import CoercedFloat, CoercedInt, Gradient
from ledfx.configuration.plugin import TypedConfig
from ledfx.effects.audio import AudioAnalysisSource, AudioReactiveEffect
from ledfx.effects.gradient import GradientEffect
from ledfx.effects.utils.custom import (
    CUSTOM_CATEGORY,
    BeatLatch,
    FloatArray,
    frame_step,
)

# Each curtain is a slow wave of its own wavelength and speed, so they drift through each other
CURTAIN_WAVES = np.array((1.0, 1.7, 2.9, 4.3, 6.1, 7.7, 9.4, 11.3))
CURTAIN_SPEEDS = np.array((0.11, -0.07, 0.17, -0.13, 0.05, 0.21, -0.19, 0.09))
# Thin vertical rays that shimmer inside the curtains
RAY_WAVE = 0.9
# A beat sends a surge of light through the sky
SURGE_DECAY = 1.5


class Aurora(AudioReactiveEffect, GradientEffect):
    NAME = "Aurora"
    CATEGORY = CUSTOM_CATEGORY
    # Effect declares HIDDEN_KEYS = None, so every list override trips bad-override.
    HIDDEN_KEYS: ClassVar[list[str]] = ["gradient_roll"]  # pyrefly: ignore[bad-override]

    class Config(GradientEffect.Config):
        gradient: Gradient = Field(
            "linear-gradient(90deg, rgb(0, 255, 120) 0%, rgb(0, 200, 170) 40%, rgb(70, 60, 255) 75%, rgb(200, 0, 200) 100%)",
            description="Colors of the northern lights",
        )
        curtains: CoercedInt = Field(
            4, description="Curtains of light drifting through each other", ge=1, le=8
        )
        speed: CoercedFloat = Field(
            1.0, description="How fast the curtains drift", ge=0.0, le=4.0
        )
        shimmer: CoercedFloat = Field(
            0.4,
            description="How much the treble makes the rays shimmer",
            ge=0.0,
            le=1.0,
        )

    config = TypedConfig(Config)

    def on_activate(self, pixel_count: int) -> None:
        self._u: FloatArray = np.arange(pixel_count) / max(pixel_count - 1, 1)
        self._time = 0.0
        self._mids = 0.0
        self._highs = 0.0
        self._surge = 0.0
        self._latch = BeatLatch()

    @override
    def audio_data_updated(self, data: AudioAnalysisSource) -> None:
        # Smoothed so the sky breathes with the music instead of flickering
        self._mids += (float(data.mids_power()) - self._mids) * 0.05
        self._highs = float(data.high_power())
        self._latch.listen(data, "Beat")

    @override
    def render(self) -> None:
        dt = frame_step(self.passed)
        self._time += dt * self.config.speed * (1 + self._mids)
        if self._latch.take(self.now):
            self._surge = 1.0
        self._surge *= float(np.exp(-dt * SURGE_DECAY))

        u, t = self._u, self._time
        count = self.config.curtains
        curtain = np.zeros_like(u)
        for wave, speed in zip(
            CURTAIN_WAVES[:count], CURTAIN_SPEEDS[:count], strict=True
        ):
            curtain += np.sin(2 * np.pi * (u * wave + t * speed) + wave)
        # Peaks of the summed waves become bright folds, the troughs dark sky
        folds = np.clip(curtain / np.sqrt(count) * 0.6 + 0.4, 0, 1) ** 2
        rays = 1 - self.config.shimmer * self._highs * 0.3 * (
            1 + np.sin(u * self.pixel_count * RAY_WAVE + 2 * np.sin(t * 1.3))
        )
        colors = self.get_gradient_color_vectorized1d(
            np.clip(0.5 + 0.5 * np.sin(2 * np.pi * (u * 0.7 + t * 0.03)) * folds, 0, 1)
        )
        level = folds * rays * (0.35 + 0.45 * self._mids + 0.4 * self._surge)
        self.pixels = np.clip(colors * level[:, None], 0, 255)
