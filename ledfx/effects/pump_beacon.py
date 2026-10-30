import numpy as np
from pydantic import Field
from typing_extensions import override

from ledfx.configuration.fields import CoercedFloat, CoercedInt, Color
from ledfx.configuration.plugin import TypedConfig
from ledfx.effects.utils.corsair import CorsairEffect, aio_layout, pump_turn, ring_gap
from ledfx.effects.utils.custom import FloatArray, color_array

# How wide the beam is, as a share of a turn
BEAM = 0.1
# The radiator fans sit to the left and the right of the pump
FAN_SIDES = np.array((0.75, 0.25))


class PumpBeacon(CorsairEffect):
    NAME = "Pump Beacon"

    class Config(CorsairEffect.Config):
        top_led: CoercedInt = Field(
            0, description="Which LED of the pump's ring is at the top", ge=0, le=15
        )
        color: Color = Field("#FFB000", description="Color of the beacon")
        turns_per_bar: CoercedFloat = Field(
            1.0, description="Turns of the beacon per bar of the song", ge=0.25, le=4.0
        )

    config = TypedConfig(Config)

    def on_activate(self, pixel_count: int) -> None:
        aio = aio_layout(pixel_count)
        self._aio = aio
        self._side: FloatArray = FAN_SIDES[np.clip(aio.fan, 0, 1)]
        self.turn = 0.0

    @override
    def config_updated(self, config: object) -> None:
        self._color = color_array(self.config.color)

    @override
    def render(self) -> None:
        self.turn += (
            self.song_moved() / 4 * self.config.turns_per_bar + self.step() * 0.05
        )
        aio = self._aio
        place = pump_turn(aio, self.config.top_led)
        beam = np.exp(-((ring_gap(place, self.turn) / BEAM) ** 2))
        # A radiator fan lights as the beam sweeps past its side
        sweep = np.exp(-((ring_gap(self._side, self.turn) / BEAM) ** 2))
        level = np.where(aio.pump, beam, sweep) * (0.6 + 0.4 * self.loudness)
        self.pixels = self._color * np.maximum(level, 0.03)[:, None]
