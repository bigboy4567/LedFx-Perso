import numpy as np
from pydantic import Field
from typing_extensions import override

from ledfx.configuration.fields import CoercedFloat, CoercedInt
from ledfx.configuration.plugin import TypedConfig
from ledfx.effects.utils.corsair import CorsairEffect, aio_layout, pump_turn
from ledfx.effects.utils.custom import heat_colors

# Past this level the radiator fans blink a warning
OVERHEAT = 0.9
UNLIT = 0.04


class PumpThermometer(CorsairEffect):
    NAME = "Pump Thermometer"

    class Config(CorsairEffect.Config):
        top_led: CoercedInt = Field(
            0, description="Which LED of the pump's ring is at the top", ge=0, le=15
        )
        sensitivity: CoercedFloat = Field(
            1.0, description="How high the music drives the temperature", ge=0.3, le=3.0
        )

    config = TypedConfig(Config)

    def on_activate(self, pixel_count: int) -> None:
        self._aio = aio_layout(pixel_count)
        self.temperature = 0.0

    @override
    def render(self) -> None:
        dt = self.step()
        target = min(1.0, self.loudness * self.config.sensitivity)
        # Heats quickly, cools slowly
        rate = 4.0 if target > self.temperature else 0.8
        self.temperature += (target - self.temperature) * min(1.0, dt * rate)

        # Up both sides of the ring at once, from the bottom to the top
        height = np.abs(pump_turn(self._aio, self.config.top_led) - 0.5) * 2
        lit = height <= self.temperature + 0.04
        pump = heat_colors(0.35 + 0.65 * height) * np.where(lit, 1.0, UNLIT)[:, None]
        warning = self.temperature > OVERHEAT and int(self.now * 6) % 2 == 0
        fans = heat_colors(np.full(height.size, 0.5)) * (1.0 if warning else 0.08)
        self.pixels = np.where(self._aio.pump[:, None], pump, fans)
