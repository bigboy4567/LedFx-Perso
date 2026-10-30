import numpy as np
from pydantic import Field
from typing_extensions import override

from ledfx.configuration.fields import CoercedFloat
from ledfx.configuration.plugin import TypedConfig
from ledfx.effects.utils.corsair import KEYBOARD_DEPTH, CorsairEffect, keyboard_layout
from ledfx.effects.utils.custom import FloatArray, hue_colors

FLASH = 6.0


class KeyColorWheel(CorsairEffect):
    NAME = "Key Color Wheel"

    class Config(CorsairEffect.Config):
        turns_per_bar: CoercedFloat = Field(
            0.25, description="Turns of the wheel per bar of the song", ge=0.0, le=2.0
        )

    config = TypedConfig(Config)

    def on_activate(self, pixel_count: int) -> None:
        board = keyboard_layout(pixel_count)
        # Each key's angle round the middle of the board, in turns
        self._angle: FloatArray = (
            np.arctan2((board.y - 0.5) * KEYBOARD_DEPTH, board.x - 0.5)
            / (2 * np.pi)
            % 1
        )
        self.turn = 0.0
        self._flash = 0.0

    @override
    def render(self) -> None:
        dt = self.step()
        self.turn += self.song_moved() / 4 * self.config.turns_per_bar + dt * 0.02
        self._flash *= float(np.exp(-dt * FLASH))
        if self.beat():
            self._flash = 1.0
        # The whole color wheel round the middle of the board, glowing brighter on each beat
        hues = (self._angle + self.turn) % 1
        self.pixels = hue_colors(hues) * (
            0.4 + 0.35 * self.loudness + 0.25 * self._flash
        )
