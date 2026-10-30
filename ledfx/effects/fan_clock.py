import time

import numpy as np
from pydantic import Field
from typing_extensions import override

from ledfx.configuration.fields import Color
from ledfx.configuration.plugin import TypedConfig
from ledfx.effects.utils.corsair import FAN_HUB, CorsairEffect, fan_layout, ring_gap
from ledfx.effects.utils.custom import FloatArray, color_array

# How wide a hand's tip is, as a share of a turn
TIP = 0.04
FLASH = 6.0
WHITE = np.array((255.0, 255.0, 255.0))


class FanClock(CorsairEffect):
    NAME = "Fan Clock"

    class Config(CorsairEffect.Config):
        hours_color: Color = Field(
            "#FF3030", description="Color of the hours, on the top fan"
        )
        minutes_color: Color = Field(
            "#30FF60", description="Color of the minutes, on the middle fan"
        )
        seconds_color: Color = Field(
            "#3080FF", description="Color of the seconds, on the bottom fan"
        )

    config = TypedConfig(Config)

    def on_activate(self, pixel_count: int) -> None:
        self._fans = fan_layout(pixel_count)
        self._flash = 0.0

    @override
    def config_updated(self, config: object) -> None:
        self._colors: FloatArray = np.array(
            [
                color_array(self.config.hours_color),
                color_array(self.config.minutes_color),
                color_array(self.config.seconds_color),
            ]
        )

    def clock(self) -> tuple[float, float, float]:
        """The time of day: hours round a 12 hour dial, minutes and seconds."""
        now = time.time()
        local = time.localtime(now)
        seconds = local.tm_sec + now % 1
        minutes = local.tm_min + seconds / 60
        return local.tm_hour % 12 + minutes / 60, minutes, seconds

    @override
    def render(self) -> None:
        self._flash *= float(np.exp(-self.step() * FLASH))
        if self.beat():
            self._flash = 1.0
        fans = self._fans
        hours, minutes, seconds = self.clock()
        # Each fan is a dial: the top one for the hours, then the minutes, then the seconds
        hands = np.array((hours / 12, minutes / 60, seconds / 60))
        role = fans.fan % 3
        hand = hands[role]
        tip = np.exp(-((ring_gap(fans.angle, hand) / TIP) ** 2))
        # The dial fills clockwise from the top up to the hand
        swept = np.where(fans.angle <= hand, 0.12, 0.02)
        level = np.maximum(tip, swept)
        rim = self._colors[role] * level[:, None]
        # The hubs tick with the beat
        hub = WHITE * max(0.03, self._flash)
        self.pixels = np.where((fans.ring == FAN_HUB)[:, None], hub, rim)
