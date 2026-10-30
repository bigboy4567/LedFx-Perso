import numpy as np
from pydantic import Field
from typing_extensions import override

from ledfx.configuration.fields import CoercedFloat, Color
from ledfx.configuration.plugin import TypedConfig
from ledfx.effects.utils.corsair import CorsairEffect, aio_layout
from ledfx.effects.utils.custom import FloatArray, color_array

# How fast a bubble pops
POP = 5.0
BUBBLE = np.array((255.0, 255.0, 255.0))


class PumpBoil(CorsairEffect):
    NAME = "Pump Boil"

    class Config(CorsairEffect.Config):
        color: Color = Field("#0050FF", description="Color of the coolant")
        boil: CoercedFloat = Field(
            1.0,
            description="How readily the music brings it to the boil",
            ge=0.2,
            le=3.0,
        )

    config = TypedConfig(Config)

    def on_activate(self, pixel_count: int) -> None:
        self._aio = aio_layout(pixel_count)
        self._bubbles: FloatArray = np.zeros(pixel_count)

    @override
    def config_updated(self, config: object) -> None:
        self._color = color_array(self.config.color)

    @override
    def render(self) -> None:
        dt = self.step()
        self._bubbles *= float(np.exp(-dt * POP))
        # The louder it gets, the more bubbles rise each second, on the pump and the fans alike
        rate = 30 * (self.loudness * self.config.boil) ** 2
        new = self._rng.random(self._bubbles.size) < rate * dt / max(
            self._bubbles.size, 1
        )
        if self.hit():
            new[self._rng.integers(self._bubbles.size)] = True
        self._bubbles[new] = 1.0
        # The coolant warms towards white as it boils
        warmth = min(1.0, self.loudness * self.config.boil)
        base = self._color * (0.25 + 0.35 * warmth)
        pixels = base + (BUBBLE - base) * self._bubbles[:, None]
        self.pixels = np.clip(pixels, 0, 255)
