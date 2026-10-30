import numpy as np
from pydantic import Field
from typing_extensions import override

from ledfx.configuration.fields import Color
from ledfx.configuration.plugin import TypedConfig
from ledfx.effects.utils.corsair import CorsairEffect, aio_layout, ring_gap
from ledfx.effects.utils.custom import color_array

# A flash dies this quickly and flickers again this long after; how wide a strike is, in turns
FLASH = 12.0
FLICKER = 0.08
STRIKE = 0.15
WHITE = np.array((255.0, 255.0, 255.0))


class PumpStorm(CorsairEffect):
    NAME = "Pump Storm"

    class Config(CorsairEffect.Config):
        cloud_color: Color = Field("#28307A", description="Color of the storm clouds")

    config = TypedConfig(Config)

    def on_activate(self, pixel_count: int) -> None:
        self._aio = aio_layout(pixel_count)
        self.flash = 0.0
        self._struck = 0.0
        self._again = np.inf
        self._time = 0.0

    @override
    def config_updated(self, config: object) -> None:
        self._cloud = color_array(self.config.cloud_color)

    @override
    def render(self) -> None:
        dt = self.step()
        self._time += dt
        self.flash *= float(np.exp(-dt * FLASH))
        self._again -= dt
        # Each percussive hit strikes somewhere round the ring, and flickers once more
        if self.hit():
            self._struck = float(self._rng.random())
            self.flash = 1.0
            self._again = FLICKER
        if self._again <= 0:
            self.flash = max(self.flash, 0.7)
            self._again = np.inf
        aio = self._aio
        # The clouds roll round the pump and rumble with the bass
        rolling = 0.5 + 0.5 * np.sin(2 * np.pi * aio.angle * 2 + self._time)
        clouds = (0.15 + 0.5 * rolling) * (0.3 + 0.7 * self.levels[0])
        pixels = self._cloud * clouds[:, None]
        strike = np.where(
            aio.pump, np.clip(1 - ring_gap(aio.angle, self._struck) / STRIKE, 0, 1), 0.6
        )
        lit = (strike * self.flash)[:, None]
        self.pixels = np.clip(pixels + (WHITE - pixels) * lit, 0, 255)
