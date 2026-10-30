import numpy as np
from pydantic import Field
from typing_extensions import override

from ledfx.configuration.fields import CoercedInt, Color
from ledfx.configuration.plugin import TypedConfig
from ledfx.effects.utils.corsair import CorsairEffect, aio_layout, pump_turn, ring_gap
from ledfx.effects.utils.custom import color_array

# A blink closes and opens the eye over this long
BLINK = 0.25
# The iris covers this share of the ring
IRIS = 0.18
WHITE = np.array((255.0, 255.0, 255.0))


class PumpEye(CorsairEffect):
    NAME = "Pump Eye"

    class Config(CorsairEffect.Config):
        top_led: CoercedInt = Field(
            0, description="Which LED of the pump's ring is at the top", ge=0, le=15
        )
        iris_color: Color = Field("#00A0FF", description="Color of the iris")
        blink_every: CoercedInt = Field(
            8, description="Beats between blinks", ge=1, le=32
        )

    config = TypedConfig(Config)

    def on_activate(self, pixel_count: int) -> None:
        self._aio = aio_layout(pixel_count)
        self._look = 0.5
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
        # The eye looks up, then left with the bass and right with the treble
        lows, _, highs = self.levels
        balance = (highs - lows) / max(lows + highs, 0.05)
        target = 0.25 * balance
        self._look += (target - self._look) * min(1.0, dt * 5)

        aio = self._aio
        place = pump_turn(aio, self.config.top_led)
        iris = np.clip(1 - ring_gap(place, self._look) / IRIS, 0, 1)
        pupil = ring_gap(place, self._look) < IRIS * 0.25
        white = WHITE * 0.25
        pixels = white + (self._iris - white) * (iris**0.5)[:, None]
        pixels[pupil] = 0.0
        # The lids close from the top and the bottom towards the middle
        if self._blinked < BLINK:
            closed = np.sin(np.pi * self._blinked / BLINK)
            height = np.abs(place - 0.5) * 2
            lid = np.abs(height - 0.5) * 2 > 1 - closed - 0.01
            pixels[lid] = 0.0
        # The radiator fans are the eyebrows: they light up with the loudness
        brows = self._iris * (0.05 + 0.6 * self.loudness)
        self.pixels = np.where(aio.pump[:, None], pixels, brows)
