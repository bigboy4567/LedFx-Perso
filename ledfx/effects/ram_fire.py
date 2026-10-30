import numpy as np
from pydantic import Field
from typing_extensions import override

from ledfx.configuration.fields import CoercedFloat
from ledfx.configuration.plugin import TypedConfig
from ledfx.effects.utils.corsair import CorsairEffect, ram_layout
from ledfx.effects.utils.custom import FloatArray, heat_colors

# The bottom of each stick always smoulders a little
EMBERS = 0.08


class RamFire(CorsairEffect):
    NAME = "RAM Fire"

    class Config(CorsairEffect.Config):
        fuel: CoercedFloat = Field(
            1.0, description="How high the music makes the flames climb", ge=0.2, le=3.0
        )
        flicker: CoercedFloat = Field(
            0.5, description="How restless the flames are", ge=0.0, le=1.0
        )

    config = TypedConfig(Config)

    def on_activate(self, pixel_count: int) -> None:
        self._ram = ram_layout(pixel_count)
        # How high the flame on each stick reaches, 0 to 1
        self._flames: FloatArray = np.full(self._ram.sticks, 0.3)

    @override
    def render(self) -> None:
        dt = self.step()
        ram = self._ram
        # Each stick burns on its own, the bass feeding them all, a little at random
        wander = 1 + self.config.flicker * (self._rng.random(ram.sticks) - 0.5)
        target = np.clip((0.2 + 0.8 * self.levels[0] * self.config.fuel) * wander, 0, 1)
        self._flames += (target - self._flames) * min(1.0, dt * 8)
        reach = self._flames[ram.stick]
        heat = np.clip(1 - ram.height / np.maximum(reach, 0.05), EMBERS, 1) ** 0.7
        flicker = 1 - self.config.flicker * 0.4 * self._rng.random(heat.size)
        self.pixels = heat_colors(heat * flicker)
