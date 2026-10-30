import numpy as np
from pydantic import Field
from typing_extensions import override

from ledfx.configuration.fields import CoercedFloat
from ledfx.configuration.plugin import TypedConfig
from ledfx.effects.utils.corsair import CorsairEffect, mat_layout
from ledfx.effects.utils.custom import FloatArray, hue_colors

# The pad remembers the mouse's colors this long, fading
TRAIL_FADE = 1.5


class MouseRainbow(CorsairEffect):
    NAME = "Mouse Rainbow"

    class Config(CorsairEffect.Config):
        turns_per_bar: CoercedFloat = Field(
            0.25,
            description="Times the mouse goes round the rainbow per bar",
            ge=0.05,
            le=2.0,
        )

    config = TypedConfig(Config)

    def on_activate(self, pixel_count: int) -> None:
        mat = mat_layout(pixel_count)
        self._along: FloatArray = mat.along
        self._mouse = mat.mouse
        self.hue = 0.0
        # The colors the mouse has shown, spreading out from beneath it round the pad
        self._trail: FloatArray = np.zeros((pixel_count, 3))

    @override
    def render(self) -> None:
        dt = self.step()
        self.hue = (
            self.hue + self.song_moved() / 4 * self.config.turns_per_bar + dt * 0.02
        ) % 1
        color = hue_colors(np.array([self.hue]))[0] * (0.4 + 0.6 * self.loudness)
        # The mouse glows through the rainbow; the pad catches its colors, the nearest first
        self._trail *= float(np.exp(-dt * TRAIL_FADE))
        near = 0.1 + 0.9 * np.clip(1 - np.abs(self._along - 0.5) * 2, 0, 1)
        self._trail = np.maximum(self._trail, np.outer(near * 0.5, color))
        self.pixels = np.where(self._mouse[:, None], color, self._trail)
