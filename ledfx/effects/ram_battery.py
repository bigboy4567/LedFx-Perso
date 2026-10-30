import numpy as np
from pydantic import Field
from typing_extensions import override

from ledfx.configuration.fields import CoercedFloat
from ledfx.configuration.plugin import TypedConfig
from ledfx.effects.utils.corsair import CorsairEffect, ram_layout
from ledfx.effects.utils.custom import FloatArray, color_array

RED = color_array("#FF1000")
YELLOW = color_array("#FFC000")
GREEN = color_array("#00FF30")
WHITE = np.array((255.0, 255.0, 255.0))
# Once every stick is charged the bank flashes this long, then empties
FULL = 0.6
UNLIT = 0.03


class RamBattery(CorsairEffect):
    NAME = "RAM Battery"

    class Config(CorsairEffect.Config):
        charge_rate: CoercedFloat = Field(
            0.5, description="Sticks charged a second at full volume", ge=0.1, le=3.0
        )

    config = TypedConfig(Config)

    def on_activate(self, pixel_count: int) -> None:
        self._ram = ram_layout(pixel_count)
        self.charges: FloatArray = np.zeros(self._ram.sticks)
        self._full = 0.0
        self._time = 0.0

    @override
    def render(self) -> None:
        dt = self.step()
        self._time += dt
        ram = self._ram
        if self._full > 0:
            self._full -= dt
            if self._full <= 0:
                self.charges[:] = 0.0
        else:
            # The music charges the sticks one after the other, from the left
            charging = int(np.argmin(self.charges >= 1))
            self.charges[charging] = min(
                1.0,
                self.charges[charging] + dt * self.config.charge_rate * self.loudness,
            )
            if (self.charges >= 1).all():
                self._full = FULL
        charge = self.charges[ram.stick]
        # Red when nearly flat, yellow, then green when charged
        low = np.clip(charge / 0.5, 0, 1)[:, None]
        high = np.clip((charge - 0.5) / 0.5, 0, 1)[:, None]
        colors = RED + (YELLOW - RED) * low + (GREEN - YELLOW) * high
        lit = ram.height <= charge + 1e-9
        # The top of the charge blinks while it fills
        filling = (charge < 1) & (np.abs(ram.height - charge) < 0.1)
        blink = 0.4 if int(self._time * 4) % 2 else 1.0
        level = np.where(lit, np.where(filling, blink, 1.0), UNLIT)
        pixels = colors * level[:, None]
        if self._full > 0:
            pixels = WHITE * (self._full / FULL) * np.ones((charge.size, 1))
        self.pixels = pixels
