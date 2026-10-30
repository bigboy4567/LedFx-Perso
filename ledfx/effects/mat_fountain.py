import numpy as np
from pydantic import Field
from typing_extensions import override

from ledfx.configuration.fields import CoercedFloat, Color
from ledfx.configuration.plugin import TypedConfig
from ledfx.effects.utils.corsair import CorsairEffect, mat_height, mat_layout
from ledfx.effects.utils.custom import FloatArray, color_array

# Drops in the air at once, at most
MAX_DROPS = 12
# In heights of a side of the U: how hard the drops fall, and how long they are
GRAVITY = 3.0
DROP = 0.1
FLASH = 6.0
WHITE = np.array((255.0, 255.0, 255.0))


class MatFountain(CorsairEffect):
    NAME = "Mat Fountain"

    class Config(CorsairEffect.Config):
        color: Color = Field("#00A0FF", description="Color of the water")
        pressure: CoercedFloat = Field(
            1.0, description="How high each beat throws the water", ge=0.3, le=2.0
        )

    config = TypedConfig(Config)

    def on_activate(self, pixel_count: int) -> None:
        mat = mat_layout(pixel_count)
        self._height: FloatArray = mat_height(mat)
        self._right = mat.along > 0.5
        self._mouse = mat.mouse
        # Each drop: its side (1 the right), how high it is, and its speed
        self._drops: FloatArray = np.zeros((0, 3))
        self._spout = 0.0

    @override
    def config_updated(self, config: object) -> None:
        self._color = color_array(self.config.color)

    @override
    def render(self) -> None:
        dt = self.step()
        self._spout *= float(np.exp(-dt * FLASH))
        # Each beat the mouse spouts water up both sides of the pad, higher with the bass
        if self.beat():
            rise = (
                np.sqrt(2 * GRAVITY)
                * self.config.pressure
                * (0.6 + 0.4 * self.levels[0])
            )
            drops = np.array([[0.0, 0.0, rise], [1.0, 0.0, rise * 0.9]])
            self._drops = np.concatenate((self._drops, drops))[-MAX_DROPS:]
            self._spout = 1.0
        if len(self._drops):
            self._drops[:, 2] -= GRAVITY * dt
            self._drops[:, 1] += self._drops[:, 2] * dt
            self._drops = self._drops[self._drops[:, 1] > -DROP]
        level = np.full(self._height.size, 0.02)
        for side, height, _ in self._drops:
            near = (self._right == (side > 0)) * np.clip(
                1 - np.abs(self._height - height) / DROP, 0, 1
            )
            np.maximum(level, near, out=level)
        pixels = self._color * level[:, None]
        mouse = self._color + (WHITE - self._color) * self._spout * 0.6
        self.pixels = np.where(
            self._mouse[:, None], mouse * max(0.1, self._spout), pixels
        )
