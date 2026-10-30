import numpy as np
from pydantic import Field
from typing_extensions import override

from ledfx.configuration.fields import Color
from ledfx.configuration.plugin import TypedConfig
from ledfx.effects.utils.corsair import CorsairEffect, mat_layout
from ledfx.effects.utils.custom import FloatArray, color_array

# How quickly a flash dies
FLASH = 18.0


class MatStrobe(CorsairEffect):
    NAME = "Mat Strobe"

    class Config(CorsairEffect.Config):
        color: Color = Field("#FFFFFF", description="Color of the flashes")

    config = TypedConfig(Config)

    def on_activate(self, pixel_count: int) -> None:
        mat = mat_layout(pixel_count)
        self._side = (mat.along > 0.5).astype(int)
        self._mouse = mat.mouse
        # How bright each side of the pad still is, and the mouse
        self._sides: FloatArray = np.zeros(2)
        self._mouse_flash = 0.0
        self._flashes = 0

    @override
    def config_updated(self, config: object) -> None:
        self._color = color_array(self.config.color)

    @override
    def render(self) -> None:
        fade = float(np.exp(-self.step() * FLASH))
        self._sides *= fade
        self._mouse_flash *= fade
        # The beats flash the two sides of the pad in turn, the percussive hits the mouse
        if self.beat():
            self._sides[self._flashes % 2] = 1.0
            self._flashes += 1
        if self.hit():
            self._mouse_flash = 1.0
        level = np.where(self._mouse, self._mouse_flash, self._sides[self._side])
        self.pixels = self._color * level[:, None]
