import numpy as np
from pydantic import Field
from typing_extensions import override

from ledfx.configuration.fields import CoercedFloat
from ledfx.configuration.plugin import TypedConfig
from ledfx.effects.utils.corsair import CorsairEffect, aio_layout
from ledfx.effects.utils.custom import FloatArray, color_array

# Pulses of coolant on their way round at once, at most
MAX_PULSES = 6
# The share of the loop the pump takes up, the rest split between the radiator fans
PUMP_SHARE = 0.6
# How long a pulse's tail is, as a share of the loop
TAIL = 0.15
HOT = color_array("#FF3000")
COLD = color_array("#0060FF")


class PumpLoop(CorsairEffect):
    NAME = "Pump Loop"

    class Config(CorsairEffect.Config):
        speed: CoercedFloat = Field(
            0.6, description="Loops a second each pulse makes", ge=0.1, le=3.0
        )

    config = TypedConfig(Config)

    def on_activate(self, pixel_count: int) -> None:
        aio = aio_layout(pixel_count)
        self._aio = aio
        # Round the pump, through the first radiator fan, then the second, and back
        fan_share = (1 - PUMP_SHARE) / 2
        self._loop: FloatArray = np.where(
            aio.pump,
            aio.angle * (PUMP_SHARE if (~aio.pump).any() else 1.0),
            PUMP_SHARE + (aio.fan + aio.angle) * fan_share,
        )
        self._pulses: FloatArray = np.zeros(0)

    @override
    def render(self) -> None:
        dt = self.step()
        # Each beat pumps a pulse of coolant into the loop
        if self.beat():
            self._pulses = np.append(self._pulses, 0.0)[-MAX_PULSES:]
        if self._pulses.size:
            self._pulses += dt * self.config.speed * (0.6 + 0.8 * self.loudness)
            self._pulses = self._pulses[self._pulses < 1 + TAIL]
        loop = self._loop
        level = np.full(loop.size, 0.05)
        for pulse in self._pulses:
            behind = pulse - loop
            np.maximum(
                level,
                np.where(
                    (behind >= -0.02) & (behind < TAIL),
                    1 - np.clip(behind, 0, TAIL) / TAIL,
                    0.0,
                ),
                out=level,
            )
        # Hot in the pump, cooling as it runs through the radiator
        cooled = np.clip((loop - PUMP_SHARE) / (1 - PUMP_SHARE), 0, 1)[:, None]
        colors = HOT + (COLD - HOT) * cooled
        self.pixels = colors * level[:, None]
