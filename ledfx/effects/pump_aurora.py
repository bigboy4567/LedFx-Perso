import numpy as np
from pydantic import Field
from typing_extensions import override

from ledfx.configuration.fields import CoercedFloat
from ledfx.configuration.plugin import TypedConfig
from ledfx.effects.utils.corsair import CorsairEffect, aio_layout, aurora_colors


class PumpAurora(CorsairEffect):
    NAME = "Pump Aurora"

    class Config(CorsairEffect.Config):
        speed: CoercedFloat = Field(
            0.4, description="How quickly the curtains drift", ge=0.1, le=2.0
        )

    config = TypedConfig(Config)

    def on_activate(self, pixel_count: int) -> None:
        self._aio = aio_layout(pixel_count)
        self._time = 0.0

    @override
    def render(self) -> None:
        # The music stirs the curtains and makes them glow
        self._time += self.step() * self.config.speed * (1 + self.loudness)
        t = self._time
        aio = self._aio
        # The radiator fans carry on the pump's curtains, a little out of step
        turn = 2 * np.pi * (aio.angle + np.where(aio.pump, 0.0, 0.3 + aio.fan * 0.4))
        curtain = 0.5 + 0.5 * np.sin(turn * 2 + t + 2 * np.sin(turn + t * 0.7))
        shade = 0.5 + 0.5 * np.sin(turn - t * 0.5)
        level = curtain**2 * (0.3 + 0.7 * self.loudness)
        self.pixels = aurora_colors(shade) * np.maximum(level, 0.04)[:, None]
