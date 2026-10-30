from typing import ClassVar

import numpy as np
from pydantic import Field
from typing_extensions import override

from ledfx.configuration.fields import CoercedFloat, CoercedInt
from ledfx.configuration.plugin import TypedConfig
from ledfx.effects.gradient import GradientEffect
from ledfx.effects.utils.corsair import CorsairEffect, aio_layout


class PumpTurbine(CorsairEffect, GradientEffect):
    NAME = "Pump Turbine"
    # Effect declares HIDDEN_KEYS = None, so every list override trips bad-override.
    HIDDEN_KEYS: ClassVar[list[str]] = ["gradient_roll"]  # pyrefly: ignore[bad-override]

    class Config(GradientEffect.Config):
        blades: CoercedInt = Field(3, description="Blades of the turbine", ge=1, le=6)
        top_speed: CoercedFloat = Field(
            3.0, description="Turns per second at full volume", ge=0.5, le=10.0
        )

    config = TypedConfig(Config)

    def on_activate(self, pixel_count: int) -> None:
        self._aio = aio_layout(pixel_count)
        self._turn = 0.0
        self.speed = 0.0

    @override
    def render(self) -> None:
        dt = self.step()
        # The turbine spins up with the music and winds down slowly when it calms
        target = 0.1 + 0.9 * self.loudness
        rate = 6.0 if target > self.speed else 1.0
        self.speed += (target - self.speed) * min(1.0, dt * rate)
        self._turn += dt * self.speed * self.config.top_speed

        aio = self._aio
        blades = self.config.blades
        behind = ((self._turn - aio.angle) * blades) % 1
        # The faster it spins, the longer the blades' blur
        tail = 8 - 6 * self.speed
        level = np.exp(-behind * tail)
        colors = self.get_gradient_color_vectorized1d(
            np.full(aio.angle.size, self.speed * 0.999)
        )
        pump = colors * level[:, None]
        # Each radiator fan is a speed gauge: its four LEDs fill with the speed
        gauge = np.where(aio.angle < self.speed, 1.0, 0.05)
        fans = colors * gauge[:, None]
        self.pixels = np.where(aio.pump[:, None], pump, fans)
