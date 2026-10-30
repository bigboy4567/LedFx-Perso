import numpy as np
from pydantic import Field
from typing_extensions import override

from ledfx.configuration.fields import CoercedInt, Color
from ledfx.configuration.plugin import TypedConfig
from ledfx.effects.utils.corsair import FAN_HUB, CorsairEffect, fan_layout, ring_gap
from ledfx.effects.utils.custom import color_array

# The iris covers this much of the rim either side of where the eye looks, in turns
IRIS = 0.15
# A blink closes and opens the eyes over this long
BLINK = 0.25
WHITE = np.array((255.0, 255.0, 255.0))


class FanEyes(CorsairEffect):
    NAME = "Fan Eyes"

    class Config(CorsairEffect.Config):
        iris_color: Color = Field("#00A0FF", description="Color of the irises")
        blink_every: CoercedInt = Field(
            8, description="Beats between blinks", ge=1, le=32
        )

    config = TypedConfig(Config)

    def on_activate(self, pixel_count: int) -> None:
        self._fans = fan_layout(pixel_count)
        self.look = 0.0
        self._beat_count = 0
        self._blinked = np.inf

    @override
    def config_updated(self, config: object) -> None:
        self._iris = color_array(self.config.iris_color)

    @override
    def render(self) -> None:
        dt = self.step()
        self._blinked += dt
        if self.beat():
            self._beat_count += 1
            if self._beat_count % self.config.blink_every == 0:
                self._blinked = 0.0
        # The eyes look up, then left with the bass and right with the treble
        lows, _, highs = self.levels
        balance = (highs - lows) / max(lows + highs, 0.05)
        self.look += (0.25 * balance - self.look) * min(1.0, dt * 5)
        fans = self._fans
        near = ring_gap(fans.angle, self.look)
        rim = np.where(near < IRIS, 1.0, 0.0)
        pixels = WHITE * 0.2 + (self._iris - WHITE * 0.2) * rim[:, None]
        # The pupil is the hub LED nearest where the eyes look; the rest of the hub is iris
        hub = fans.ring == FAN_HUB
        pupil = hub & (near < 0.13)
        pixels = np.where(hub[:, None], self._iris, pixels)
        pixels[pupil] = 0.0
        # The lids close from the top and the bottom
        if self._blinked < BLINK:
            closed = np.sin(np.pi * self._blinked / BLINK)
            lid = np.abs(np.cos(2 * np.pi * fans.angle)) > 1 - closed - 0.01
            pixels[lid | (hub & (closed > 0.6))] = 0.0
        self.pixels = pixels
