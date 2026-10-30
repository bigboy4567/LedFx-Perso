import numpy as np
from pydantic import Field
from typing_extensions import override

from ledfx.configuration.fields import CoercedFloat
from ledfx.configuration.plugin import TypedConfig
from ledfx.effects.utils.corsair import CorsairEffect, fan_layout, fan_xy
from ledfx.effects.utils.custom import FloatArray, heat_colors

EMBERS = 0.08


class FanFire(CorsairEffect):
    NAME = "Fan Fire"

    class Config(CorsairEffect.Config):
        fuel: CoercedFloat = Field(
            1.0, description="How high the bass makes the flames climb", ge=0.2, le=3.0
        )
        flicker: CoercedFloat = Field(
            0.5, description="How restless the flames are", ge=0.0, le=1.0
        )

    config = TypedConfig(Config)

    def on_activate(self, pixel_count: int) -> None:
        fans = fan_layout(pixel_count)
        _, y = fan_xy(fans)
        # Flames burn up from the bottom of each fan
        self._rise: FloatArray = (1 - y) / 2
        self._flame = 0.3

    @override
    def render(self) -> None:
        target = 0.25 + 0.75 * min(1.0, self.levels[0] * self.config.fuel)
        self._flame += (target - self._flame) * min(1.0, self.step() * 8)
        # The lower an LED on its fan, the hotter; the flame's height follows the bass
        # Embers glow even where the flames do not reach
        heat = np.clip(self._rise * 1.3 - (1 - self._flame), EMBERS, 1) ** 0.8
        flicker = 1 - self.config.flicker * 0.5 * self._rng.random(heat.size)
        self.pixels = heat_colors(heat * flicker)
