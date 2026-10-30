from typing import Literal

import numpy as np
from pydantic import Field
from typing_extensions import override

from ledfx.configuration.fields import CoercedInt, Color
from ledfx.configuration.plugin import TypedConfig
from ledfx.effects.audio import AudioAnalysisSource, AudioReactiveEffect
from ledfx.effects.utils.custom import (
    CUSTOM_CATEGORY,
    BeatLatch,
    FloatArray,
    color_array,
    frame_step,
)

# Light thins out with distance from the sun
FALLOFF = 2.0
# Drifting clouds hide the sun by at most this much
CLOUD_SHADE = 0.7
WHITE = np.array((255.0, 255.0, 255.0))

Source = Literal["At the start", "In the middle"]


class GodRays(AudioReactiveEffect):
    NAME = "God Rays"
    CATEGORY = CUSTOM_CATEGORY

    class Config(AudioReactiveEffect.Config):
        color: Color = Field("#FFE6A8", description="Color of the sunlight")
        rays: CoercedInt = Field(10, description="Rays of light", ge=2, le=40)
        source: Source = Field(
            "At the start", description="Where the sun sits along the strip"
        )

    config = TypedConfig(Config)

    def on_activate(self, pixel_count: int) -> None:
        self._u: FloatArray = np.arange(pixel_count) / max(pixel_count - 1, 1)
        self._time = 0.0
        self._peek = 0.0
        self._mids = 0.0
        self._latch = BeatLatch()

    @override
    def config_updated(self, config: object) -> None:
        self._color = color_array(self.config.color)

    @override
    def audio_data_updated(self, data: AudioAnalysisSource) -> None:
        self._mids += (float(data.mids_power()) - self._mids) * 0.1
        self._latch.listen(data, "Beat")

    def distance(self) -> FloatArray:
        if self.config.source == "At the start":
            return self._u
        return np.abs(self._u - 0.5) * 2

    def clouds(self) -> float:
        """How much the drifting clouds hide the sun right now, 0 to 1."""
        t = self._time
        return float(0.5 + 0.5 * np.sin(t * 0.4) * np.sin(t * 0.13 + 1))

    @override
    def render(self) -> None:
        dt = frame_step(self.passed)
        self._time += dt
        self._peek *= float(np.exp(-dt * 2))
        if self._latch.take(self.now):
            # The sun peeks through a gap in the clouds
            self._peek = 1.0

        d = self.distance()
        # Rays spread apart with distance, as beams from a far-off sun do
        rays = 0.5 + 0.5 * np.sin(
            2 * np.pi * (self.config.rays * np.sqrt(d) - self._time * 0.05)
        )
        shade = 1 - CLOUD_SHADE * self.clouds() * (1 - self._peek)
        light = np.exp(-d * FALLOFF) * (0.35 + 0.65 * rays**2)
        level = light * shade * (
            0.5 + 0.5 * min(1.0, self._mids * 2)
        ) + 0.4 * self._peek * np.exp(-d * 4)
        pixels = self._color * np.clip(level, 0, 1)[:, None]
        sun = np.exp(-((d / 0.03) ** 2))[:, None] * shade
        self.pixels = np.clip(pixels + (WHITE - pixels) * sun, 0, 255)
