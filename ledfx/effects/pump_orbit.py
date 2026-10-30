import numpy as np
from pydantic import Field
from typing_extensions import override

from ledfx.configuration.fields import Color
from ledfx.configuration.plugin import TypedConfig
from ledfx.effects.utils.corsair import CorsairEffect, aio_layout, ring_gap
from ledfx.effects.utils.custom import color_array

# How big a moon is, as a share of a turn
MOON = 0.06
FLASH = 4.0
WHITE = np.array((255.0, 255.0, 255.0))


class PumpOrbit(CorsairEffect):
    NAME = "Pump Orbit"

    class Config(CorsairEffect.Config):
        bass_color: Color = Field(
            "#FF4000", description="Color of the moon the bass drives"
        )
        treble_color: Color = Field(
            "#00C0FF", description="Color of the moon the treble drives"
        )

    config = TypedConfig(Config)

    def on_activate(self, pixel_count: int) -> None:
        self._aio = aio_layout(pixel_count)
        self.bass = 0.0
        self.treble = 0.5
        self._together = False
        self._flash = 0.0

    @override
    def config_updated(self, config: object) -> None:
        self._bass = color_array(self.config.bass_color)
        self._treble = color_array(self.config.treble_color)

    @override
    def render(self) -> None:
        dt = self.step()
        # The bass's moon goes clockwise and the treble's the other way, each at its band's pace
        self.bass = (self.bass + dt * (0.1 + 1.2 * self.levels[0])) % 1
        self.treble = (self.treble - dt * (0.1 + 1.2 * self.levels[2])) % 1
        self._flash *= float(np.exp(-dt * FLASH))
        # The radiator fans flash each time the moons pass each other
        gap = float(ring_gap(self.bass, self.treble))
        if gap < 0.04 and not self._together:
            self._flash = 1.0
            self._together = True
        elif gap > 0.1:
            self._together = False
        aio = self._aio
        bass = np.exp(-((ring_gap(aio.angle, self.bass) / MOON) ** 2))
        treble = np.exp(-((ring_gap(aio.angle, self.treble) / MOON) ** 2))
        pump = self._bass * bass[:, None] + self._treble * treble[:, None]
        fans = WHITE * max(0.03, self._flash)
        self.pixels = np.clip(np.where(aio.pump[:, None], pump, fans), 0, 255)
