import numpy as np
from pydantic import Field
from typing_extensions import override

from ledfx.configuration.fields import Color
from ledfx.configuration.plugin import TypedConfig
from ledfx.effects.utils.corsair import FAN_HUB, CorsairEffect, fan_layout
from ledfx.effects.utils.custom import FloatArray, color_array

# Shooting stars at once, at most
MAX_SHOOTING = 4
# A shooting star crosses this much of a rim, as a share of a turn, in this many seconds
STREAK = 0.6
STREAK_TIME = 0.4
MOON = np.array((255.0, 230.0, 170.0))
WHITE = np.array((255.0, 255.0, 255.0))


class FanStarfield(CorsairEffect):
    NAME = "Fan Starfield"

    class Config(CorsairEffect.Config):
        star_color: Color = Field("#A0C0FF", description="Color of the stars")

    config = TypedConfig(Config)

    def on_activate(self, pixel_count: int) -> None:
        self._fans = fan_layout(pixel_count)
        self._phase: FloatArray = self._rng.random(pixel_count) * 2 * np.pi
        self._rate: FloatArray = 1 + self._rng.random(pixel_count) * 2
        # Each shooting star: its fan, where on the rim it set off, and how long ago
        self._shooting: FloatArray = np.zeros((0, 3))
        self._time = 0.0

    @override
    def config_updated(self, config: object) -> None:
        self._star = color_array(self.config.star_color)

    @override
    def render(self) -> None:
        dt = self.step()
        self._time += dt
        fans = self._fans
        # Each percussive hit sends a shooting star across a rim
        if self.hit():
            star = np.array([[self._rng.integers(fans.count), self._rng.random(), 0.0]])
            self._shooting = np.concatenate((self._shooting, star))[-MAX_SHOOTING:]
        if len(self._shooting):
            self._shooting[:, 2] += dt
            self._shooting = self._shooting[self._shooting[:, 2] < STREAK_TIME]

        twinkle = (0.5 + 0.5 * np.sin(self._time * self._rate + self._phase)) ** 4
        pixels = self._star * (0.03 + 0.5 * twinkle)[:, None]
        for fan, start, age in self._shooting:
            head = start + STREAK * age / STREAK_TIME
            behind = (head - fans.angle) % 1
            streak = np.where(
                (fans.fan == fan) & (behind < 0.15), 1 - behind / 0.15, 0.0
            )
            streak *= 1 - age / STREAK_TIME
            np.maximum(pixels, WHITE * streak[:, None], out=pixels)
        # The hub is a moon, waxing with the bass
        moon = MOON * (0.1 + 0.6 * self.levels[0])
        self.pixels = np.where((fans.ring == FAN_HUB)[:, None], moon, pixels)
