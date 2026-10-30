import numpy as np
from pydantic import Field
from typing_extensions import override

from ledfx.configuration.fields import CoercedFloat
from ledfx.configuration.plugin import TypedConfig
from ledfx.effects.utils.corsair import FAN_HUB, CorsairEffect, fan_layout
from ledfx.effects.utils.custom import FloatArray, color_array

RED = color_array("#FF1000")
YELLOW = color_array("#FFC000")
GREEN = color_array("#00FF30")
WHITE = np.array((255.0, 255.0, 255.0))
# Once every fan is charged the stack flashes this long, then empties
FULL = 0.6
UNLIT = 0.03


class FanBattery(CorsairEffect):
    NAME = "Fan Battery"

    class Config(CorsairEffect.Config):
        charge_rate: CoercedFloat = Field(
            0.4, description="Fans charged a second at full volume", ge=0.1, le=3.0
        )

    config = TypedConfig(Config)

    def on_activate(self, pixel_count: int) -> None:
        self._fans = fan_layout(pixel_count)
        self.charges: FloatArray = np.zeros(self._fans.count)
        self._full = 0.0
        self._time = 0.0

    @override
    def render(self) -> None:
        dt = self.step()
        self._time += dt
        fans = self._fans
        if self._full > 0:
            self._full -= dt
            if self._full <= 0:
                self.charges[:] = 0.0
        else:
            # The music charges the fans one after the other, from the bottom one up
            order = np.arange(fans.count)[::-1]
            charging = int(order[np.argmin(self.charges[order] >= 1)])
            self.charges[charging] = min(
                1.0,
                self.charges[charging] + dt * self.config.charge_rate * self.loudness,
            )
            if (self.charges >= 1).all():
                self._full = FULL
        charge = self.charges[fans.fan]
        # Red when nearly flat, yellow, then green when charged
        low = np.clip(charge / 0.5, 0, 1)[:, None]
        high = np.clip((charge - 0.5) / 0.5, 0, 1)[:, None]
        colors = RED + (YELLOW - RED) * low + (GREEN - YELLOW) * high
        # Each rim fills clockwise from the top; the hub of the fan charging blinks
        lit = fans.angle < charge - 1e-9
        hub = fans.ring == FAN_HUB
        charging = (charge > 0) & (charge < 1)
        blink = 1.0 if int(self._time * 3) % 2 else 0.2
        level = np.where(
            hub,
            np.where(charging, blink, np.where(charge >= 1, 1.0, UNLIT)),
            np.where(lit, 1.0, UNLIT),
        )
        pixels = colors * level[:, None]
        if self._full > 0:
            pixels = WHITE * (self._full / FULL) * np.ones((charge.size, 1))
        self.pixels = pixels
