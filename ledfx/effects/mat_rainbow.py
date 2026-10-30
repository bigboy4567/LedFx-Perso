import numpy as np
from pydantic import Field
from typing_extensions import override

from ledfx.configuration.fields import CoercedFloat
from ledfx.configuration.plugin import TypedConfig
from ledfx.effects.utils.corsair import CorsairEffect, mat_layout
from ledfx.effects.utils.custom import FloatArray, hue_colors


class MatRainbow(CorsairEffect):
    NAME = "Mat Rainbow"

    class Config(CorsairEffect.Config):
        repeats: CoercedFloat = Field(
            1.0, description="Rainbows round the pad's edge", ge=0.25, le=4.0
        )
        jump: CoercedFloat = Field(
            0.1, description="How far each beat jolts the rainbow round", ge=0.0, le=0.5
        )

    config = TypedConfig(Config)

    def on_activate(self, pixel_count: int) -> None:
        mat = mat_layout(pixel_count)
        self._along: FloatArray = mat.along
        self._mouse = mat.mouse
        self.shift = 0.0
        self._jolt = 0.0

    @override
    def render(self) -> None:
        dt = self.step()
        # The rainbow drifts round with the song, and each beat jolts it on, easing in
        if self.beat():
            self._jolt += self.config.jump
        eased = self._jolt * min(1.0, dt * 10)
        self._jolt -= eased
        self.shift += eased + self.song_moved() * 0.05 + dt * 0.03
        # The mouse shows the hue at the bottom of the U, beneath it
        along = np.where(self._mouse, 0.5, self._along)
        hues = (along * self.config.repeats - self.shift) % 1
        self.pixels = hue_colors(hues) * (0.5 + 0.5 * self.loudness)
