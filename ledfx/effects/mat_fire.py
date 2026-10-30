import numpy as np
from pydantic import Field
from typing_extensions import override

from ledfx.configuration.fields import CoercedFloat
from ledfx.configuration.plugin import TypedConfig
from ledfx.effects.utils.corsair import CorsairEffect, mat_height, mat_layout
from ledfx.effects.utils.custom import FloatArray, heat_colors

# The bottom of the pad always smoulders a little
EMBERS = 0.08


class MatFire(CorsairEffect):
    NAME = "Mat Fire"

    class Config(CorsairEffect.Config):
        fuel: CoercedFloat = Field(
            1.0, description="How high the bass makes the flames climb", ge=0.2, le=3.0
        )
        flicker: CoercedFloat = Field(
            0.5, description="How restless the flames are", ge=0.0, le=1.0
        )

    config = TypedConfig(Config)

    def on_activate(self, pixel_count: int) -> None:
        mat = mat_layout(pixel_count)
        self._height: FloatArray = mat_height(mat)
        self._mouse = mat.mouse
        # The two sides burn on their own: which side each LED is on
        self._right = mat.along > 0.5
        self._flames: FloatArray = np.full(2, 0.3)

    @override
    def render(self) -> None:
        dt = self.step()
        # The flames climb both sides of the pad from the bottom, fed by the bass
        wander = 1 + self.config.flicker * (self._rng.random(2) - 0.5)
        target = np.clip((0.2 + 0.8 * self.levels[0] * self.config.fuel) * wander, 0, 1)
        self._flames += (target - self._flames) * min(1.0, dt * 8)
        reach = self._flames[self._right.astype(int)]
        heat = np.clip(1 - self._height / np.maximum(reach, 0.05), EMBERS, 1) ** 0.7
        flicker = 1 - self.config.flicker * 0.4 * self._rng.random(heat.size)
        # The mouse is a coal glowing with the fire's strength
        coal = float(self._flames.mean()) * (
            1 - self.config.flicker * 0.3 * self._rng.random()
        )
        heat = np.where(self._mouse, coal, heat * flicker)
        self.pixels = heat_colors(heat)
