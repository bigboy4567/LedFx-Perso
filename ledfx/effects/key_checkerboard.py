import numpy as np
from pydantic import Field
from typing_extensions import override

from ledfx.configuration.fields import CoercedFloat, Color
from ledfx.configuration.plugin import TypedConfig
from ledfx.effects.utils.corsair import KEYBOARD_DEPTH, CorsairEffect, keyboard_layout
from ledfx.effects.utils.custom import BoolArray, color_array

FLASH = 5.0


class KeyCheckerboard(CorsairEffect):
    NAME = "Key Checkerboard"

    class Config(CorsairEffect.Config):
        first_color: Color = Field("#FF00A0", description="Color of one set of squares")
        second_color: Color = Field("#00E0FF", description="Color of the other set")
        square: CoercedFloat = Field(
            0.08,
            description="How wide a square is, as a share of the board",
            ge=0.03,
            le=0.3,
        )

    config = TypedConfig(Config)

    def on_activate(self, pixel_count: int) -> None:
        board = keyboard_layout(pixel_count)
        self._x = board.x
        self._y = board.y * KEYBOARD_DEPTH
        self.swapped = False
        self._flash = 0.0

    @override
    def config_updated(self, config: object) -> None:
        self._first = color_array(self.config.first_color)
        self._second = color_array(self.config.second_color)

    def squares(self) -> BoolArray:
        """Which keys are on the first set of squares."""
        square = self.config.square
        cells = np.floor(self._x / square) + np.floor(self._y / square)
        return cells % 2 == 0

    @override
    def render(self) -> None:
        self._flash *= float(np.exp(-self.step() * FLASH))
        # Each beat the squares swap colors
        if self.beat():
            self.swapped = not self.swapped
            self._flash = 1.0
        first = self.squares() != self.swapped
        colors = np.where(first[:, None], self._first, self._second)
        self.pixels = colors * (0.35 + 0.35 * self.loudness + 0.3 * self._flash)
