import numpy as np
from pydantic import Field
from typing_extensions import override

from ledfx.configuration.fields import CoercedFloat
from ledfx.configuration.plugin import TypedConfig
from ledfx.effects.utils.corsair import FAN_HUB, CorsairEffect, fan_layout
from ledfx.effects.utils.custom import color_array

# The lamps from the top fan down, as on a traffic light
LAMPS = np.array([color_array(color) for color in ("#FF0000", "#FFA000", "#00FF30")])
RED, AMBER, GREEN = range(3)
# An unlit lamp still shows its color, faintly
UNLIT = 0.04
PULSE = 6.0


class FanTrafficLight(CorsairEffect):
    NAME = "Fan Traffic Light"

    class Config(CorsairEffect.Config):
        beats_per_cycle: CoercedFloat = Field(
            4.0,
            description="Beats of the song from green, through amber and red, back to green",
            ge=2.0,
            le=16.0,
        )

    config = TypedConfig(Config)

    def on_activate(self, pixel_count: int) -> None:
        self._fans = fan_layout(pixel_count)
        self._pulse = 0.0

    def lamp(self) -> int:
        """The lamp lit now: green for half the cycle, amber a quarter, red a quarter."""
        cycle = (self.song.beats / self.config.beats_per_cycle) % 1
        if cycle < 0.5:
            return GREEN
        return AMBER if cycle < 0.75 else RED

    @override
    def render(self) -> None:
        self._pulse *= float(np.exp(-self.step() * PULSE))
        if self.beat():
            self._pulse = 1.0
        fans = self._fans
        lamp = self.lamp()
        if fans.count >= len(LAMPS):
            lamps = fans.fan % len(LAMPS)
        else:
            # Too few fans for a lamp each: every fan shows the lamp that is lit
            lamps = np.full(fans.fan.size, lamp)
        lit = lamps == lamp
        colors = LAMPS[lamps]
        # The lit lamp's hub throbs with the beat
        hub = fans.ring == FAN_HUB
        level = np.where(lit, np.where(hub, 0.6 + 0.4 * self._pulse, 1.0), UNLIT)
        self.pixels = colors * level[:, None]
