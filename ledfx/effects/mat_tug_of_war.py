import numpy as np
from pydantic import Field
from typing_extensions import override

from ledfx.configuration.fields import Color
from ledfx.configuration.plugin import TypedConfig
from ledfx.effects.utils.corsair import CorsairEffect, mat_layout
from ledfx.effects.utils.custom import FloatArray, color_array

# The rope's knot, as a share of the pad's edge
KNOT = 0.04
WHITE = np.array((255.0, 255.0, 255.0))


class MatTugOfWar(CorsairEffect):
    NAME = "Mat Tug of War"

    class Config(CorsairEffect.Config):
        bass_color: Color = Field(
            "#FF2000", description="Color of the bass's team, on the left"
        )
        treble_color: Color = Field(
            "#00C0FF", description="Color of the treble's team, on the right"
        )

    config = TypedConfig(Config)

    def on_activate(self, pixel_count: int) -> None:
        mat = mat_layout(pixel_count)
        self._along: FloatArray = mat.along
        self._mouse = mat.mouse
        # Where the knot is: the bass pulls it to the right, the treble to the left
        self.knot = 0.5

    @override
    def config_updated(self, config: object) -> None:
        self._bass = color_array(self.config.bass_color)
        self._treble = color_array(self.config.treble_color)

    @override
    def render(self) -> None:
        dt = self.step()
        lows, _, highs = self.levels
        pull = (lows - highs) / max(lows + highs, 0.05)
        self.knot += (0.5 + 0.45 * pull - self.knot) * min(1.0, dt * 3)
        # Each beat tugs the rope a little, one way or the other
        if self.beat():
            self.knot = float(
                np.clip(self.knot + (self._rng.random() - 0.5) * 0.1, 0.05, 0.95)
            )
        along = self._along
        left = along < self.knot
        pixels = np.where(left[:, None], self._bass, self._treble) * (
            0.4 + 0.6 * self.loudness
        )
        knot = np.abs(along - self.knot) < KNOT
        pixels = np.where(knot[:, None], WHITE, pixels)
        # The mouse shows the team that is winning
        winning = self._bass if self.knot > 0.5 else self._treble
        self.pixels = np.where(self._mouse[:, None], winning, pixels)
