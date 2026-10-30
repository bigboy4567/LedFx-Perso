import numpy as np
from pydantic import Field
from typing_extensions import override

from ledfx.configuration.fields import Color
from ledfx.configuration.plugin import TypedConfig
from ledfx.effects.utils.corsair import BAR, LOGO, CorsairEffect, keyboard_layout
from ledfx.effects.utils.custom import FloatArray, IntArray, color_array

# The keys strobe in thirds, from left to right
THIRDS = 3
# How quickly a flash dies
FLASH = 18.0


class KeyStrobe(CorsairEffect):
    NAME = "Key Strobe"

    class Config(CorsairEffect.Config):
        color: Color = Field("#FFFFFF", description="Color of the flashes")

    config = TypedConfig(Config)

    def on_activate(self, pixel_count: int) -> None:
        board = keyboard_layout(pixel_count)
        self._third: IntArray = np.minimum((board.x * THIRDS).astype(int), THIRDS - 1)
        self._bar = board.zone == BAR
        self._logo = board.zone == LOGO
        self._flash: FloatArray = np.zeros(THIRDS)
        self._flashes = 0
        self._bar_flash = 0.0

    @override
    def config_updated(self, config: object) -> None:
        self._color = color_array(self.config.color)

    @override
    def render(self) -> None:
        fade = float(np.exp(-self.step() * FLASH))
        self._flash *= fade
        self._bar_flash *= fade
        # Each beat flashes the next third of the keys and the logo
        if self.beat():
            self._flash[self._flashes % THIRDS] = 1.0
            self._flashes += 1
        # Each percussive hit flashes the light bar
        if self.hit():
            self._bar_flash = 1.0
        level = self._flash[self._third]
        level = np.where(self._bar, self._bar_flash, level)
        level = np.where(self._logo, float(self._flash.max()), level)
        self.pixels = self._color * level[:, None]
