import numpy as np
from pydantic import Field
from typing_extensions import override

from ledfx.configuration.fields import CoercedInt, Color
from ledfx.configuration.plugin import TypedConfig
from ledfx.effects.utils.corsair import CorsairEffect, aio_layout, pump_turn
from ledfx.effects.utils.custom import color_array

# A ping reaches the bottom of the ring this long after it is sent
TRAVEL = 0.5
# How wide the wave is, as a share of the way down
WAVE = 0.08
# The echo coming back is this much fainter
ECHO = 0.4
FLASH = 5.0


class PumpSonar(CorsairEffect):
    NAME = "Pump Sonar"

    class Config(CorsairEffect.Config):
        top_led: CoercedInt = Field(
            0, description="Which LED of the pump's ring is at the top", ge=0, le=15
        )
        color: Color = Field("#00FF90", description="Color of the pings")

    config = TypedConfig(Config)

    def on_activate(self, pixel_count: int) -> None:
        self._aio = aio_layout(pixel_count)
        self.since = np.inf
        self._found = 0.0

    @override
    def config_updated(self, config: object) -> None:
        self._color = color_array(self.config.color)

    @override
    def render(self) -> None:
        dt = self.step()
        before = self.since / TRAVEL
        self.since += dt
        self._found *= float(np.exp(-dt * FLASH))
        if self.beat():
            self.since = 0.0
        front = self.since / TRAVEL
        # The ping reaches the bottom and finds the radiator, which lights up
        if before < 1 <= front:
            self._found = 1.0
        aio = self._aio
        down = 1 - np.abs(pump_turn(aio, self.config.top_led) - 0.5) * 2
        if front <= 1:
            wave = np.exp(-(((down - front) / WAVE) ** 2))
        else:
            # The echo climbs back up, fainter
            wave = ECHO * np.exp(-(((down - (2 - front)) / WAVE) ** 2)) * (front < 2)
        pump = self._color * np.maximum(wave, 0.03)[:, None]
        fans = self._color * max(0.03, self._found)
        self.pixels = np.where(aio.pump[:, None], pump, fans)
