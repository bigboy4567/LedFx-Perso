import numpy as np
from pydantic import Field
from typing_extensions import override

from ledfx.configuration.fields import Color
from ledfx.configuration.plugin import TypedConfig
from ledfx.effects.utils.corsair import CorsairEffect, mat_height, mat_layout
from ledfx.effects.utils.custom import FloatArray, color_array

UNLIT = 0.04


class MatSplit(CorsairEffect):
    NAME = "Mat Split"

    class Config(CorsairEffect.Config):
        bass_color: Color = Field(
            "#FF2000", description="Color of the bass, on the left side"
        )
        treble_color: Color = Field(
            "#00C0FF", description="Color of the treble, on the right side"
        )
        mids_color: Color = Field(
            "#40FF40", description="Color of the mids, on the mouse"
        )

    config = TypedConfig(Config)

    def on_activate(self, pixel_count: int) -> None:
        mat = mat_layout(pixel_count)
        self._height: FloatArray = mat_height(mat)
        self._right = mat.along > 0.5
        self._mouse = mat.mouse

    @override
    def config_updated(self, config: object) -> None:
        self._bass = color_array(self.config.bass_color)
        self._treble = color_array(self.config.treble_color)
        self._mids = color_array(self.config.mids_color)

    @override
    def render(self) -> None:
        lows, mids, highs = self.levels
        # Each side of the U is a meter climbing from the bottom to its tip
        level = np.where(self._right, highs, lows)
        lit = self._height <= level + 0.04
        color = np.where(self._right[:, None], self._treble, self._bass)
        pixels = color * np.where(lit, 1.0, UNLIT)[:, None]
        # The mouse sits between them, with the mids
        mouse = self._mids * (UNLIT + (1 - UNLIT) * mids)
        self.pixels = np.where(self._mouse[:, None], mouse, pixels)
