import numpy as np
from pydantic import Field
from typing_extensions import override

from ledfx.configuration.fields import Color
from ledfx.configuration.plugin import TypedConfig
from ledfx.effects.utils.corsair import CorsairEffect, fan_layout
from ledfx.effects.utils.custom import FloatArray, color_array

# A flash of lightning dies this quickly, and flickers again this long after
FLASH = 12.0
FLICKER = 0.08
WHITE = np.array((255.0, 255.0, 255.0))


class FanStorm(CorsairEffect):
    NAME = "Fan Storm"

    class Config(CorsairEffect.Config):
        cloud_color: Color = Field("#28307A", description="Color of the storm clouds")

    config = TypedConfig(Config)

    def on_activate(self, pixel_count: int) -> None:
        self._fans = fan_layout(pixel_count)
        self._flash: FloatArray = np.zeros(self._fans.count)
        # The fan struck last, and how long until its lightning flickers again
        self._struck = 0
        self._again = np.inf
        self._time = 0.0

    @override
    def config_updated(self, config: object) -> None:
        self._cloud = color_array(self.config.cloud_color)

    @override
    def render(self) -> None:
        dt = self.step()
        self._time += dt
        self._flash *= float(np.exp(-dt * FLASH))
        self._again -= dt
        # A percussive hit strikes a fan, and its lightning flickers once more
        if self.hit():
            self._struck = int(self._rng.integers(self._fans.count))
            self._flash[self._struck] = 1.0
            self._again = FLICKER
        if self._again <= 0:
            self._flash[self._struck] = max(self._flash[self._struck], 0.7)
            self._again = np.inf
        fans = self._fans
        # The clouds roll round the fans and rumble with the bass
        rolling = 0.5 + 0.5 * np.sin(2 * np.pi * fans.angle * 2 + self._time + fans.fan)
        clouds = (0.15 + 0.5 * rolling) * (0.3 + 0.7 * self.levels[0])
        flash = self._flash[fans.fan][:, None]
        pixels = self._cloud * clouds[:, None]
        self.pixels = np.clip(pixels + (WHITE - pixels) * flash, 0, 255)
