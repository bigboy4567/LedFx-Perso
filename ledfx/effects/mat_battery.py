import numpy as np
from pydantic import Field
from typing_extensions import override

from ledfx.configuration.fields import CoercedFloat
from ledfx.configuration.plugin import TypedConfig
from ledfx.effects.utils.corsair import CorsairEffect, mat_layout
from ledfx.effects.utils.custom import FloatArray, color_array

RED = color_array("#FF1000")
YELLOW = color_array("#FFC000")
GREEN = color_array("#00FF30")
WHITE = np.array((255.0, 255.0, 255.0))
# Once charged the pad flashes this long, then empties
FULL = 0.6
UNLIT = 0.03


class MatBattery(CorsairEffect):
    NAME = "Mat Battery"

    class Config(CorsairEffect.Config):
        charge_rate: CoercedFloat = Field(
            0.3, description="Full charges a second at full volume", ge=0.05, le=2.0
        )

    config = TypedConfig(Config)

    def on_activate(self, pixel_count: int) -> None:
        mat = mat_layout(pixel_count)
        self._along: FloatArray = mat.along
        self._mouse = mat.mouse
        self.charge = 0.0
        self._full = 0.0
        self._time = 0.0

    @override
    def render(self) -> None:
        dt = self.step()
        self._time += dt
        if self._full > 0:
            self._full -= dt
            if self._full <= 0:
                self.charge = 0.0
        else:
            # The music charges the pad from its left tip round to its right
            self.charge = min(
                1.0, self.charge + dt * self.config.charge_rate * self.loudness
            )
            if self.charge >= 1:
                self._full = FULL
        charge = self.charge
        low, high = min(1.0, charge / 0.5), max(0.0, (charge - 0.5) / 0.5)
        color = RED + (YELLOW - RED) * low + (GREEN - YELLOW) * high
        lit = self._along < charge - 1e-9
        pixels = color * np.where(lit, 1.0, UNLIT)[:, None]
        # The mouse blinks while it charges
        blink = 0.8 if int(self._time * 3) % 2 else 0.1
        pixels = np.where(self._mouse[:, None], color * blink, pixels)
        if self._full > 0:
            pixels = WHITE * (self._full / FULL) * np.ones((self._along.size, 1))
        self.pixels = pixels
