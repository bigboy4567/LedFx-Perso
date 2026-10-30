import numpy as np
from pydantic import Field
from typing_extensions import override

from ledfx.configuration.fields import Color
from ledfx.configuration.plugin import TypedConfig
from ledfx.effects.utils.corsair import CorsairEffect, mat_layout
from ledfx.effects.utils.custom import FloatArray, color_array

# A flicker goes out for this long
FLICKER = 0.07


class MatNeon(CorsairEffect):
    NAME = "Mat Neon"

    class Config(CorsairEffect.Config):
        tube_color: Color = Field(
            "#FF2090", description="Color of the neon tube round the pad"
        )
        mouse_color: Color = Field("#20E0FF", description="Color of the mouse's neon")

    config = TypedConfig(Config)

    def on_activate(self, pixel_count: int) -> None:
        mat = mat_layout(pixel_count)
        self._along: FloatArray = mat.along
        self._mouse = mat.mouse
        # How long until each stretch of tube, or the mouse, comes back on
        self._dark_left: FloatArray = np.zeros(3)
        self._time = 0.0

    @override
    def config_updated(self, config: object) -> None:
        self._tube = color_array(self.config.tube_color)
        self._mouse_color = color_array(self.config.mouse_color)

    @override
    def render(self) -> None:
        dt = self.step()
        self._time += dt
        self._dark_left -= dt
        # Like an old neon sign, a stretch of tube flickers out on a percussive hit
        if self.hit():
            self._dark_left[self._rng.integers(3)] = FLICKER * (1 + self._rng.random())
        # The tube hums, a little brighter with the music
        hum = 0.75 + 0.05 * np.sin(self._time * 120) + 0.2 * self.loudness
        stretch = np.minimum((self._along * 2).astype(int), 1)
        stretch = np.where(self._mouse, 2, stretch)
        on = self._dark_left[stretch] <= 0
        colors = np.where(self._mouse[:, None], self._mouse_color, self._tube)
        self.pixels = colors * np.where(on, hum, 0.04)[:, None]
