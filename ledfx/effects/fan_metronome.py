import numpy as np
from pydantic import Field
from typing_extensions import override

from ledfx.configuration.fields import CoercedFloat, Color
from ledfx.configuration.plugin import TypedConfig
from ledfx.effects.utils.corsair import FAN_HUB, CorsairEffect, fan_layout, ring_gap
from ledfx.effects.utils.custom import color_array

# The arm's tip lights this far either side of it, as a share of a turn
TIP = 0.05
TICK_FADE = 8.0
WHITE = np.array((255.0, 255.0, 255.0))


class FanMetronome(CorsairEffect):
    NAME = "Fan Metronome"

    class Config(CorsairEffect.Config):
        color: Color = Field("#FFB040", description="Color of the metronome's arm")
        swing: CoercedFloat = Field(
            0.2,
            description="How far the arm swings either side of the top, as a share of a turn",
            ge=0.05,
            le=0.45,
        )

    config = TypedConfig(Config)

    def on_activate(self, pixel_count: int) -> None:
        self._fans = fan_layout(pixel_count)
        self._tick = 0.0

    @override
    def config_updated(self, config: object) -> None:
        self._color = color_array(self.config.color)

    @override
    def render(self) -> None:
        self._tick *= float(np.exp(-self.step() * TICK_FADE))
        if self.beat():
            self._tick = 1.0
        fans = self._fans
        swing = self.config.swing
        # One swing a beat, from one side of the top to the other
        tip = swing * np.sin(np.pi * self.song.beats)
        arm = np.exp(-((ring_gap(fans.angle, tip) / TIP) ** 2))
        # Faint marks where the arm turns back
        ends = (ring_gap(fans.angle, swing) < TIP) | (
            ring_gap(fans.angle, -swing) < TIP
        )
        level = np.maximum(arm, np.where(ends, 0.1, 0.0))
        rim = self._color * level[:, None]
        # The hubs tick on every beat
        hub = WHITE * max(0.04, self._tick)
        self.pixels = np.where((fans.ring == FAN_HUB)[:, None], hub, rim)
