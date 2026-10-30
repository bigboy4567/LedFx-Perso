import numpy as np
from pydantic import Field
from typing_extensions import override

from ledfx.configuration.fields import Color
from ledfx.configuration.plugin import TypedConfig
from ledfx.effects.utils.corsair import BAR, CorsairEffect, keyboard_layout
from ledfx.effects.utils.custom import FloatArray, color_array

UNLIT = 0.04


class KeySplit(CorsairEffect):
    NAME = "Key Split"

    class Config(CorsairEffect.Config):
        bass_color: Color = Field(
            "#FF2000", description="Color of the bass, on the left"
        )
        treble_color: Color = Field(
            "#00C0FF", description="Color of the treble, on the right"
        )
        mids_color: Color = Field(
            "#40FF40", description="Color of the mids, on the light bar"
        )

    config = TypedConfig(Config)

    def on_activate(self, pixel_count: int) -> None:
        board = keyboard_layout(pixel_count)
        self._x: FloatArray = board.x
        self._right = board.x > 0.5
        self._bar = board.zone == BAR
        # How far in from its own edge each key is, 0 at the edge to 1 in the middle
        self._reach: FloatArray = 1 - np.abs(board.x - 0.5) * 2
        self._shown: FloatArray = np.zeros(3)

    @override
    def config_updated(self, config: object) -> None:
        self._bass = color_array(self.config.bass_color)
        self._treble = color_array(self.config.treble_color)
        self._mids = color_array(self.config.mids_color)

    @override
    def render(self) -> None:
        self._shown += (self.levels - self._shown) * min(1.0, self.step() * 15)
        lows, mids, highs = self._shown
        # The bass fills in from the left edge, the treble from the right, meeting in the middle
        level = np.where(self._right, highs, lows)
        lit = self._reach < level
        color = np.where(self._right[:, None], self._treble, self._bass)
        pixels = color * np.where(lit, 1.0, UNLIT)[:, None]
        # The light bar fills from the middle out with the mids
        bar_lit = (1 - self._reach) < mids
        bar = self._mids * np.where(bar_lit, 1.0, UNLIT)[:, None]
        self.pixels = np.where(self._bar[:, None], bar, pixels)
