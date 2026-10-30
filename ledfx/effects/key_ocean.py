import numpy as np
from pydantic import Field
from typing_extensions import override

from ledfx.configuration.fields import CoercedFloat, Color
from ledfx.configuration.plugin import TypedConfig
from ledfx.effects.utils.corsair import CorsairEffect, keyboard_layout
from ledfx.effects.utils.custom import FloatArray, color_array

WHITE = np.array((255.0, 255.0, 255.0))


class KeyOcean(CorsairEffect):
    NAME = "Key Ocean"

    class Config(CorsairEffect.Config):
        water_color: Color = Field("#0050FF", description="Color of the water")
        waves_per_beat: CoercedFloat = Field(
            0.5, description="Waves rolling in per beat of the song", ge=0.1, le=2.0
        )

    config = TypedConfig(Config)

    def on_activate(self, pixel_count: int) -> None:
        board = keyboard_layout(pixel_count)
        self._x: FloatArray = board.x
        # How far in from the front of the board, 0 at the front row
        self._inland: FloatArray = 1 - board.y
        self._rolled = 0.0

    @override
    def config_updated(self, config: object) -> None:
        self._water = color_array(self.config.water_color)

    @override
    def render(self) -> None:
        self._rolled += (
            self.song_moved() * self.config.waves_per_beat + self.step() * 0.1
        )
        # The waves roll in from the front row towards the light bar, a little slanted
        place = self._inland * 2 + 0.3 * np.sin(self._x * 6) - self._rolled
        swell = 0.5 + 0.5 * np.cos(2 * np.pi * place)
        # The bass makes the sea rougher: the crests rise and foam
        rough = 0.3 + 0.7 * self.levels[0]
        crest = swell**8 * rough
        pixels = self._water * (0.15 + 0.5 * swell * rough)[:, None]
        self.pixels = pixels + (WHITE - pixels) * crest[:, None]
