import numpy as np
from pydantic import Field
from typing_extensions import override

from ledfx.configuration.fields import CoercedFloat
from ledfx.configuration.plugin import TypedConfig
from ledfx.effects.utils.corsair import CorsairEffect, keyboard_layout
from ledfx.effects.utils.custom import FloatArray, heat_colors

# The bottom row always smoulders a little
EMBERS = 0.06


class KeyFire(CorsairEffect):
    NAME = "Key Fire"

    class Config(CorsairEffect.Config):
        fuel: CoercedFloat = Field(
            1.0, description="How high the bass makes the flames climb", ge=0.2, le=3.0
        )
        flicker: CoercedFloat = Field(
            0.5, description="How restless the flames are", ge=0.0, le=1.0
        )

    config = TypedConfig(Config)

    def on_activate(self, pixel_count: int) -> None:
        board = keyboard_layout(pixel_count)
        self._x: FloatArray = board.x
        # Height up the board, 0 at the front row to 1 at the light bar
        self._rise: FloatArray = 1 - board.y
        self._flame = 0.3
        self._time = 0.0

    @override
    def render(self) -> None:
        dt = self.step()
        self._time += dt * (1 + 2 * self.config.flicker)
        target = 0.2 + 0.8 * min(1.0, self.levels[0] * self.config.fuel)
        self._flame += (target - self._flame) * min(1.0, dt * 8)
        # Tongues of flame along the board, each rising and falling on its own
        t = self._time
        x = self._x
        tongues = (
            0.75 + 0.25 * (np.sin(x * 23 + t * 3.1) + np.sin(x * 41 - t * 4.3)) / 2
        )
        reach = self._flame * tongues
        heat = np.clip(1 - self._rise / np.maximum(reach, 0.05), EMBERS, 1) ** 0.8
        flicker = 1 - self.config.flicker * 0.4 * self._rng.random(heat.size)
        self.pixels = heat_colors(heat * flicker)
