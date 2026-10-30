import numpy as np
from pydantic import Field
from typing_extensions import override

from ledfx.configuration.fields import CoercedInt, Color
from ledfx.configuration.plugin import TypedConfig
from ledfx.effects.utils.corsair import CorsairEffect, mat_layout
from ledfx.effects.utils.custom import color_array

FLASH = 8.0
WHITE = np.array((255.0, 255.0, 255.0))


class MatSiren(CorsairEffect):
    NAME = "Mat Siren"

    class Config(CorsairEffect.Config):
        left_color: Color = Field("#FF0000", description="Color of the left side")
        right_color: Color = Field("#0030FF", description="Color of the right side")
        flashes_per_beat: CoercedInt = Field(
            4, description="Flashes of a side on each beat", ge=1, le=8
        )

    config = TypedConfig(Config)

    def on_activate(self, pixel_count: int) -> None:
        mat = mat_layout(pixel_count)
        self._right = mat.along > 0.5
        self._mouse = mat.mouse
        self._flash = 0.0
        self.beats = 0.0

    @override
    def config_updated(self, config: object) -> None:
        self._left_color = color_array(self.config.left_color)
        self._right_color = color_array(self.config.right_color)

    @override
    def render(self) -> None:
        dt = self.step()
        self._flash *= float(np.exp(-dt * FLASH))
        if self.beat():
            self._flash = 1.0
        # Keeps time with the song, or at 120 beats a minute while it is silent
        moved = self.song_moved()
        self.beats += moved if moved > 0 else dt * 2
        # One side then the other, a beat each, flashing a few times on its beat
        right = int(self.beats) % 2 == 1
        on = (self.beats * self.config.flashes_per_beat) % 1 < 0.5
        side = np.where((self._right == right) & on, 1.0, 0.03)
        colors = np.where(self._right[:, None], self._right_color, self._left_color)
        pixels = colors * side[:, None]
        # The mouse flashes white on the beat
        self.pixels = np.where(
            self._mouse[:, None], WHITE * max(0.03, self._flash), pixels
        )
