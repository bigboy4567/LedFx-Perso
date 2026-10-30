import numpy as np
from pydantic import Field
from typing_extensions import override

from ledfx.configuration.fields import CoercedFloat
from ledfx.configuration.plugin import TypedConfig
from ledfx.effects.utils.corsair import KEYBOARD_DEPTH, CorsairEffect, keyboard_layout
from ledfx.effects.utils.custom import FloatArray, hue_colors

FLASH = 6.0


class KeyRainbow(CorsairEffect):
    NAME = "Key Rainbow"

    class Config(CorsairEffect.Config):
        tilt: CoercedFloat = Field(
            30.0,
            description="Angle of the rainbow's bands, in degrees",
            ge=-90.0,
            le=90.0,
        )
        repeats: CoercedFloat = Field(
            1.0, description="Rainbows across the board", ge=0.25, le=4.0
        )
        speed: CoercedFloat = Field(
            0.25,
            description="Rainbows flowing past per beat of the song",
            ge=0.0,
            le=2.0,
        )

    config = TypedConfig(Config)

    def on_activate(self, pixel_count: int) -> None:
        board = keyboard_layout(pixel_count)
        self._x: FloatArray = board.x
        self._y: FloatArray = board.y * KEYBOARD_DEPTH
        self._shift = 0.0
        self._flash = 0.0

    @override
    def render(self) -> None:
        dt = self.step()
        self._shift += self.song_moved() * self.config.speed + dt * 0.03
        self._flash *= float(np.exp(-dt * FLASH))
        if self.beat():
            self._flash = 1.0
        tilt = np.radians(self.config.tilt)
        along = self._x * np.cos(tilt) + self._y * np.sin(tilt)
        hues = (along * self.config.repeats - self._shift) % 1
        # Each beat makes the whole rainbow glow brighter for a moment
        self.pixels = hue_colors(hues) * (
            0.45 + 0.35 * self.loudness + 0.2 * self._flash
        )
