import numpy as np
from pydantic import Field
from typing_extensions import override

from ledfx.configuration.fields import CoercedFloat
from ledfx.configuration.plugin import TypedConfig
from ledfx.effects.utils.corsair import CorsairEffect, aurora_colors, keyboard_layout
from ledfx.effects.utils.custom import FloatArray


class KeyAurora(CorsairEffect):
    NAME = "Key Aurora"

    class Config(CorsairEffect.Config):
        speed: CoercedFloat = Field(
            0.4, description="How quickly the curtains drift", ge=0.1, le=2.0
        )

    config = TypedConfig(Config)

    def on_activate(self, pixel_count: int) -> None:
        board = keyboard_layout(pixel_count)
        self._x: FloatArray = board.x
        self._y: FloatArray = board.y
        self._time = 0.0

    @override
    def render(self) -> None:
        # The music stirs the curtains and makes them glow
        self._time += self.step() * self.config.speed * (1 + self.loudness)
        t = self._time
        x, y = self._x, self._y
        curtain = 0.5 + 0.5 * np.sin(x * 9 + t + 2 * np.sin(x * 3 - t * 0.6 + y))
        shade = 0.5 + 0.5 * np.sin(x * 4 - t * 0.4 + y * 2)
        # The curtains hang from the light bar and fade towards the front of the board
        level = curtain**2 * (1 - 0.7 * y) * (0.3 + 0.7 * self.loudness)
        self.pixels = aurora_colors(shade) * np.maximum(level, 0.03)[:, None]
