from typing import ClassVar

import numpy as np
from pydantic import Field
from typing_extensions import override

from ledfx.configuration.fields import CoercedFloat, CoercedInt
from ledfx.configuration.plugin import TypedConfig
from ledfx.effects.gradient import GradientEffect
from ledfx.effects.utils.corsair import FAN_HUB, CorsairEffect, fan_layout, ring_gap

# Each moon of a fan orbits this much faster than the one before it
MOON_SPEEDS = (1.0, 1.6, 2.5)
# A moon is this wide, as a share of its orbit
MOON_SIZE = 0.05
WHITE = np.array((255.0, 255.0, 255.0))


class FanPlanets(CorsairEffect, GradientEffect):
    NAME = "Fan Planets"
    # Effect declares HIDDEN_KEYS = None, so every list override trips bad-override.
    HIDDEN_KEYS: ClassVar[list[str]] = ["gradient_roll"]  # pyrefly: ignore[bad-override]

    class Config(GradientEffect.Config):
        moons: CoercedInt = Field(2, description="Moons orbiting each fan", ge=1, le=3)
        orbits_per_beat: CoercedFloat = Field(
            0.25,
            description="Orbits of the slowest moon per beat of the song",
            ge=0.05,
            le=2.0,
        )

    config = TypedConfig(Config)

    def on_activate(self, pixel_count: int) -> None:
        self._fans = fan_layout(pixel_count)
        self._orbit = 0.0
        self._flash = 0.0

    @override
    def render(self) -> None:
        dt = self.step()
        self._orbit += self.song_moved() * self.config.orbits_per_beat + dt * 0.03
        self._flash *= float(np.exp(-dt * 5))
        if self.beat():
            self._flash = 1.0

        fans = self._fans
        level = np.zeros(fans.angle.size)
        for moon in range(self.config.moons):
            # Every fan's moons start from a different place, and go round each other way
            heading = np.where(fans.fan % 2 == 0, 1.0, -1.0)
            at = (
                self._orbit * MOON_SPEEDS[moon] * heading + fans.fan * 0.37 + moon / 3
            ) % 1
            np.maximum(
                level, np.exp(-((ring_gap(fans.angle, at) / MOON_SIZE) ** 2)), out=level
            )
        moons = self.get_gradient_color_vectorized1d(np.full(level.size, 0.6))
        # The hub is the sun, glowing with the bass
        sun = self.get_gradient_color_vectorized1d(np.full(level.size, 0.1))
        hub = (fans.ring == FAN_HUB)[:, None]
        sun_level = 0.3 + 0.7 * self.levels[0]
        pixels = np.where(hub, sun * sun_level, moons * level[:, None])
        self.pixels = np.clip(
            pixels + (WHITE - pixels) * (level * self._flash * 0.6)[:, None], 0, 255
        )
