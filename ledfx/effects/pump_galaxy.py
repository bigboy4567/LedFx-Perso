from typing import ClassVar

import numpy as np
from pydantic import Field
from typing_extensions import override

from ledfx.configuration.fields import CoercedFloat, CoercedInt
from ledfx.configuration.plugin import TypedConfig
from ledfx.effects.gradient import GradientEffect
from ledfx.effects.utils.corsair import CorsairEffect, aio_layout
from ledfx.effects.utils.custom import FloatArray

WHITE = np.array((255.0, 255.0, 255.0))


class PumpGalaxy(CorsairEffect, GradientEffect):
    NAME = "Pump Galaxy"
    # Effect declares HIDDEN_KEYS = None, so every list override trips bad-override.
    HIDDEN_KEYS: ClassVar[list[str]] = ["gradient_roll"]  # pyrefly: ignore[bad-override]

    class Config(GradientEffect.Config):
        arms: CoercedInt = Field(2, description="Spiral arms of the galaxy", ge=1, le=4)
        speed: CoercedFloat = Field(
            0.15, description="Turns a second when the music is quiet", ge=0.02, le=1.0
        )

    config = TypedConfig(Config)

    def on_activate(self, pixel_count: int) -> None:
        self._aio = aio_layout(pixel_count)
        self._phase: FloatArray = self._rng.random(pixel_count) * 2 * np.pi
        self._rate: FloatArray = 1 + self._rng.random(pixel_count) * 3
        self._turn = 0.0
        self._time = 0.0

    @override
    def render(self) -> None:
        dt = self.step()
        self._time += dt
        # The galaxy turns faster as the music gets louder
        self._turn += dt * self.config.speed * (1 + 2 * self.loudness)
        aio = self._aio
        arms = (
            0.5 + 0.5 * np.cos(2 * np.pi * (aio.angle * self.config.arms - self._turn))
        ) ** 3
        colors = self.get_gradient_color_vectorized1d(
            (aio.angle + self._turn) % 1 * 0.999
        )
        # Stars twinkle between the arms and across the radiator
        stars = (0.5 + 0.5 * np.sin(self._time * self._rate + self._phase)) ** 8
        pump = np.maximum(
            colors * (0.8 * arms)[:, None], WHITE * (0.5 * stars)[:, None]
        )
        fans = WHITE * (0.03 + 0.6 * stars)[:, None]
        self.pixels = np.where(aio.pump[:, None], pump, fans)
