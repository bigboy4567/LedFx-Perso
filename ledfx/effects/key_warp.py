import numpy as np
from pydantic import Field
from typing_extensions import override

from ledfx.configuration.fields import CoercedFloat, Color
from ledfx.configuration.plugin import TypedConfig
from ledfx.effects.utils.corsair import KEYBOARD_DEPTH, CorsairEffect, keyboard_layout
from ledfx.effects.utils.custom import FloatArray, color_array

STARS = 30
# Stars are reborn near the middle once they are this far out
FAR = 0.6
CENTRE = np.array((0.5, 0.5 * KEYBOARD_DEPTH))


class KeyWarp(CorsairEffect):
    NAME = "Key Warp"

    class Config(CorsairEffect.Config):
        color: Color = Field("#C0D0FF", description="Color of the stars")
        warp: CoercedFloat = Field(
            1.0,
            description="How fast the music sends the stars streaming past",
            ge=0.2,
            le=4.0,
        )

    config = TypedConfig(Config)

    def on_activate(self, pixel_count: int) -> None:
        board = keyboard_layout(pixel_count)
        self._x: FloatArray = board.x
        self._y: FloatArray = board.y * KEYBOARD_DEPTH
        # Each star: its heading out from the middle, and how far out it is
        self._headings: FloatArray = self._rng.random(STARS) * 2 * np.pi
        self._distances: FloatArray = self._rng.random(STARS) * FAR

    @override
    def config_updated(self, config: object) -> None:
        self._color = color_array(self.config.color)

    @override
    def render(self) -> None:
        dt = self.step()
        # The stars stream out faster the further out they are, and the louder the music
        rate = self.config.warp * (0.3 + 2 * self.loudness)
        self._distances += dt * rate * (0.03 + self._distances * 1.5)
        gone = self._distances > FAR
        self._distances[gone] = self._rng.random(int(gone.sum())) * 0.05
        self._headings[gone] = self._rng.random(int(gone.sum())) * 2 * np.pi
        level = np.zeros(self._x.size)
        for heading, distance in zip(self._headings, self._distances, strict=True):
            at = CENTRE + distance * np.array((np.cos(heading), np.sin(heading)))
            # Stars swell as they come closer
            size = 0.03 + distance * 0.08
            near = np.clip(1 - np.hypot(self._x - at[0], self._y - at[1]) / size, 0, 1)
            np.maximum(level, near * min(1.0, distance * 6), out=level)
        self.pixels = self._color * np.maximum(level, 0.01)[:, None]
