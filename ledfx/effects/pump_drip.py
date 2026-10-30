import numpy as np
from pydantic import Field
from typing_extensions import override

from ledfx.configuration.fields import CoercedInt, Color
from ledfx.configuration.plugin import TypedConfig
from ledfx.effects.utils.corsair import CorsairEffect, aio_layout, pump_turn
from ledfx.effects.utils.custom import FloatArray, color_array

# Drops sliding down at once, at most
MAX_DROPS = 4
# How long a drop is, as a share of the way down
DROP = 0.12
SPLASH_FADE = 5.0
WHITE = np.array((255.0, 255.0, 255.0))


class PumpDrip(CorsairEffect):
    NAME = "Pump Drip"

    class Config(CorsairEffect.Config):
        top_led: CoercedInt = Field(
            0, description="Which LED of the pump's ring is at the top", ge=0, le=15
        )
        color: Color = Field("#00C0FF", description="Color of the drops")

    config = TypedConfig(Config)

    def on_activate(self, pixel_count: int) -> None:
        self._aio = aio_layout(pixel_count)
        # A drop swells at the top until a beat lets it go
        self.forming = 0.0
        # How far down each falling drop is, 0 at the top to 1 at the bottom
        self._drops: FloatArray = np.zeros(0)
        self._splash = 0.0

    @override
    def config_updated(self, config: object) -> None:
        self._color = color_array(self.config.color)

    @override
    def render(self) -> None:
        dt = self.step()
        self.forming = min(1.0, self.forming + dt * (0.5 + self.loudness))
        self._splash *= float(np.exp(-dt * SPLASH_FADE))
        if self.beat() and self.forming > 0.3:
            self._drops = np.append(self._drops, 0.0)[-MAX_DROPS:]
            self.forming = 0.0
        if self._drops.size:
            # The drops slide down both sides of the ring, gathering speed
            self._drops += dt * (0.5 + 2 * self._drops)
            landed = self._drops >= 1
            if landed.any():
                self._splash = 1.0
            self._drops = self._drops[~landed]

        aio = self._aio
        down = 1 - np.abs(pump_turn(aio, self.config.top_led) - 0.5) * 2
        level = np.where(down < 0.07, 0.15 + 0.85 * self.forming, 0.03)
        for drop in self._drops:
            np.maximum(level, np.clip(1 - np.abs(down - drop) / DROP, 0, 1), out=level)
        # Each drop splashes on the radiator below
        pump = self._color * level[:, None]
        fans = self._color + (WHITE - self._color) * self._splash**2
        self.pixels = np.where(aio.pump[:, None], pump, fans * max(0.03, self._splash))
