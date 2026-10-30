import numpy as np
from pydantic import Field
from typing_extensions import override

from ledfx.configuration.fields import Color
from ledfx.configuration.plugin import TypedConfig
from ledfx.effects.utils.corsair import CorsairEffect, mat_layout
from ledfx.effects.utils.custom import FloatArray, color_array

# Shooting stars at once, at most
MAX_SHOOTING = 3
# A shooting star crosses the pad in this many seconds, trailing this far behind
CROSSING = 0.6
TAIL = 0.2
MOON = np.array((255.0, 230.0, 170.0))
WHITE = np.array((255.0, 255.0, 255.0))


class MatStarfield(CorsairEffect):
    NAME = "Mat Starfield"

    class Config(CorsairEffect.Config):
        star_color: Color = Field("#A0C0FF", description="Color of the stars")

    config = TypedConfig(Config)

    def on_activate(self, pixel_count: int) -> None:
        mat = mat_layout(pixel_count)
        self._along: FloatArray = mat.along
        self._mouse = mat.mouse
        self._phase: FloatArray = self._rng.random(pixel_count) * 2 * np.pi
        self._rate: FloatArray = 1 + self._rng.random(pixel_count) * 2
        # Each shooting star: its heading (1 rightward) and how long ago it set off
        self._shooting: FloatArray = np.zeros((0, 2))
        self._time = 0.0

    @override
    def config_updated(self, config: object) -> None:
        self._star = color_array(self.config.star_color)

    @override
    def render(self) -> None:
        dt = self.step()
        self._time += dt
        # Each percussive hit sends a shooting star round the pad from one tip or the other
        if self.hit():
            star = np.array([[1.0 if self._rng.random() < 0.5 else -1.0, 0.0]])
            self._shooting = np.concatenate((self._shooting, star))[-MAX_SHOOTING:]
        if len(self._shooting):
            self._shooting[:, 1] += dt
            self._shooting = self._shooting[
                self._shooting[:, 1] < CROSSING * (1 + TAIL)
            ]
        twinkle = (0.5 + 0.5 * np.sin(self._time * self._rate + self._phase)) ** 4
        pixels = self._star * (0.03 + 0.5 * twinkle)[:, None]
        for heading, age in self._shooting:
            place = self._along if heading > 0 else 1 - self._along
            behind = age / CROSSING - place
            streak = np.where((behind >= 0) & (behind < TAIL), 1 - behind / TAIL, 0.0)
            np.maximum(pixels, WHITE * streak[:, None], out=pixels)
        # The mouse is the moon, waxing with the bass
        moon = MOON * (0.1 + 0.6 * self.levels[0])
        self.pixels = np.where(self._mouse[:, None], moon, pixels)
