from typing import ClassVar

import numpy as np
from pydantic import Field
from typing_extensions import override

from ledfx.configuration.fields import CoercedFloat
from ledfx.configuration.plugin import TypedConfig
from ledfx.effects.audio import AudioAnalysisSource, AudioReactiveEffect
from ledfx.effects.gradient import GradientEffect
from ledfx.effects.utils.custom import (
    CUSTOM_CATEGORY,
    BeatLatch,
    FloatArray,
    Trigger,
    frame_step,
)

# Share of each repeat that is lit, and how dim the rest is
DUTY = 0.6
OFF_LEVEL = 0.15


class Stutter(AudioReactiveEffect, GradientEffect):
    NAME = "Stutter"
    CATEGORY = CUSTOM_CATEGORY
    # Effect declares HIDDEN_KEYS = None, so every list override trips bad-override.
    HIDDEN_KEYS: ClassVar[list[str]] = ["gradient_roll"]  # pyrefly: ignore[bad-override]

    class Config(GradientEffect.Config):
        slice_size: CoercedFloat = Field(
            0.125,
            description="Share of the strip caught and repeated on a hit",
            ge=0.03,
            le=0.5,
        )
        repeats: CoercedFloat = Field(
            16.0, description="Repeats per second while stuttering", ge=4.0, le=32.0
        )
        length: CoercedFloat = Field(
            0.4, description="Seconds a stutter lasts", ge=0.1, le=1.5
        )
        trigger: Trigger = Field(
            "Beat", description="Stutter on the bass or on every percussive hit"
        )

    config = TypedConfig(Config)

    def on_activate(self, pixel_count: int) -> None:
        self._x = np.arange(pixel_count)
        self._u: FloatArray = self._x / max(pixel_count - 1, 1)
        self._time = 0.0
        self._age = np.inf
        self._slice: FloatArray = np.zeros((1, 3))
        self._latch = BeatLatch()

    @override
    def config_updated(self, config: object) -> None:
        if not hasattr(self, "_rng"):
            self._rng = np.random.default_rng()

    @override
    def audio_data_updated(self, data: AudioAnalysisSource) -> None:
        self._latch.listen(data, self.config.trigger)

    def _flowing(self) -> FloatArray:
        u, t = self._u, self._time
        colors = self.get_gradient_color_vectorized1d((u * 1.5 + t) % 1)
        bands = (0.5 + 0.5 * np.sin(2 * np.pi * (u * 4 - t * 3))) ** 2
        return colors * (0.2 + 0.8 * bands)[:, None]

    @override
    def render(self) -> None:
        dt = frame_step(self.passed)
        self._time += dt * 0.15
        self._age += dt
        flowing = self._flowing()
        n = self.pixel_count
        if self._latch.take(self.now):
            # Catch a slice of what is playing, from anywhere along the strip
            size = max(1, round(self.config.slice_size * n))
            start = int(self._rng.integers(0, max(n - size, 0) + 1))
            self._slice = flowing[start : start + size].copy()
            self._age = 0.0
        if self._age >= self.config.length:
            self.pixels = flowing
            return
        # The caught slice repeats along the strip, gated on and off in quick time
        gate = 1.0 if (self._age * self.config.repeats) % 1 < DUTY else OFF_LEVEL
        self.pixels = self._slice[self._x % len(self._slice)] * gate
