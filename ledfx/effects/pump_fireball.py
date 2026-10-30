import numpy as np
from pydantic import Field
from typing_extensions import override

from ledfx.configuration.fields import CoercedFloat
from ledfx.configuration.plugin import TypedConfig
from ledfx.effects.utils.corsair import CorsairEffect, aio_layout
from ledfx.effects.utils.custom import heat_colors

# The fireball's trail, as a share of a turn
TRAIL = 0.5


class PumpFireball(CorsairEffect):
    NAME = "Pump Fireball"

    class Config(CorsairEffect.Config):
        top_speed: CoercedFloat = Field(
            1.5, description="Turns a second on a heavy bass", ge=0.3, le=5.0
        )

    config = TypedConfig(Config)

    def on_activate(self, pixel_count: int) -> None:
        self._aio = aio_layout(pixel_count)
        self.at = 0.0

    @override
    def render(self) -> None:
        dt = self.step()
        # The bass drives the fireball round the ring
        self.at = (self.at + dt * (0.15 + self.config.top_speed * self.levels[0])) % 1
        aio = self._aio
        behind = (self.at - aio.angle) % 1
        trail = np.clip(1 - behind / TRAIL, 0, 1) ** 1.5
        # The radiator fans are embers, glowing with the bass
        flicker = 1 - 0.3 * self._rng.random(trail.size)
        embers = (0.15 + 0.45 * self.levels[0]) * flicker
        heat = np.where(aio.pump, trail, embers)
        self.pixels = heat_colors(np.maximum(heat, 0.03))
