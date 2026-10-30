from typing import Literal

import numpy as np
from pydantic import Field
from typing_extensions import override

from ledfx.configuration.fields import CoercedFloat, CoercedInt
from ledfx.configuration.plugin import TypedConfig
from ledfx.effects.audio import AudioAnalysisSource, AudioReactiveEffect
from ledfx.effects.utils.custom import (
    CUSTOM_CATEGORY,
    FloatArray,
    color_array,
    frame_step,
    splat,
)

SAND = color_array("#D2A460")
DUST = color_array("#5A3A18")
# The wind blows at least this fast, in strips per second, and the bass adds gusts
CALM = 0.15
GUST = 0.8

Wind = Literal["Toward the end", "Toward the start"]


class Sandstorm(AudioReactiveEffect):
    NAME = "Sandstorm"
    CATEGORY = CUSTOM_CATEGORY

    class Config(AudioReactiveEffect.Config):
        grains: CoercedInt = Field(
            150, description="Grains of sand in the air", ge=10, le=400
        )
        gusts: CoercedFloat = Field(
            1.0, description="How hard the bass makes the wind gust", ge=0.0, le=3.0
        )
        haze: CoercedFloat = Field(
            0.3, description="How thick the dust haze is", ge=0.0, le=1.0
        )
        wind: Wind = Field("Toward the end", description="Which way the wind blows")

    config = TypedConfig(Config)

    def on_activate(self, pixel_count: int) -> None:
        self._x: FloatArray = np.arange(pixel_count, dtype=float)
        self._u: FloatArray = self._x / max(pixel_count - 1, 1)
        self._lift()
        self._gust = 0.0
        self._time = 0.0

    def _lift(self) -> None:
        count = self.config.grains
        # Positions in strip lengths, how fast each grain rides the wind, and how big it is
        self.grains: FloatArray = self._rng.random(count)
        self._drag: FloatArray = self._rng.uniform(0.5, 1.5, count)
        self._size: FloatArray = self._rng.uniform(0.3, 1.0, count)

    @override
    def config_updated(self, config: object) -> None:
        if not hasattr(self, "_rng"):
            self._rng = np.random.default_rng()
        if hasattr(self, "grains") and self.grains.size != self.config.grains:
            self._lift()

    @override
    def audio_data_updated(self, data: AudioAnalysisSource) -> None:
        self._gust += (float(data.lows_power()) - self._gust) * 0.08

    def wind(self) -> float:
        return CALM + GUST * self.config.gusts * self._gust

    @override
    def render(self) -> None:
        dt = frame_step(self.passed)
        self._time += dt
        count = self.grains.size
        swirl = self._rng.normal(0, 0.03, count)
        self.grains = (self.grains + (self.wind() * self._drag + swirl) * dt) % 1

        n = self.pixel_count
        # The haze rolls along with the wind, thicker in the gusts
        roll = 0.6 + 0.4 * np.sin(2 * np.pi * (self._u * 2 - self._time * self.wind()))
        haze = self.config.haze * (0.3 + 0.7 * self._gust) * roll
        pixels = DUST * haze[:, None]
        level = np.zeros(n)
        width = max(0.5, n / 300)
        for grain, size in zip(self.grains * (n - 1), self._size, strict=True):
            splat(level, self._x, float(grain), width * size * 1.5, float(size))
        pixels = np.maximum(pixels, SAND * level[:, None])
        pixels = np.clip(pixels, 0, 255)
        self.pixels = pixels if self.config.wind == "Toward the end" else pixels[::-1]
