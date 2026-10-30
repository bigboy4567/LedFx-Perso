import numpy as np
from pydantic import Field
from typing_extensions import override

from ledfx.configuration.fields import CoercedInt, Color
from ledfx.configuration.plugin import TypedConfig
from ledfx.effects.utils.corsair import CorsairEffect, aio_layout, pump_turn
from ledfx.effects.utils.custom import color_array

UNLIT = 0.04


class PumpSplit(CorsairEffect):
    NAME = "Pump Split"

    class Config(CorsairEffect.Config):
        top_led: CoercedInt = Field(
            0, description="Which LED of the pump's ring is at the top", ge=0, le=15
        )
        bass_color: Color = Field(
            "#FF2000", description="Color of the bass, on the left"
        )
        treble_color: Color = Field(
            "#00C0FF", description="Color of the treble, on the right"
        )

    config = TypedConfig(Config)

    def on_activate(self, pixel_count: int) -> None:
        self._aio = aio_layout(pixel_count)

    @override
    def config_updated(self, config: object) -> None:
        self._bass = color_array(self.config.bass_color)
        self._treble = color_array(self.config.treble_color)

    @override
    def render(self) -> None:
        aio = self._aio
        place = pump_turn(aio, self.config.top_led)
        # Each half of the ring is a meter climbing from the bottom to the top
        right = place < 0.5
        height = np.where(right, 1 - place * 2, (place - 0.5) * 2)
        lows, _, highs = self.levels
        level = np.where(right, highs, lows)
        lit = height <= level + 0.03
        pump = (
            np.where(right[:, None], self._treble, self._bass)
            * np.where(lit, 1.0, UNLIT)[:, None]
        )
        # The first radiator fan pulses with the bass, the second with the treble
        fan_level = np.where(aio.fan == 0, lows, highs)
        fan_color = np.where((aio.fan == 0)[:, None], self._bass, self._treble)
        fans = fan_color * (UNLIT + (1 - UNLIT) * fan_level)[:, None]
        self.pixels = np.where(aio.pump[:, None], pump, fans)
