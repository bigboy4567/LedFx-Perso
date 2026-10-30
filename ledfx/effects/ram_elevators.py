from typing import ClassVar

import numpy as np
from pydantic import Field
from typing_extensions import override

from ledfx.configuration.fields import CoercedFloat
from ledfx.configuration.plugin import TypedConfig
from ledfx.effects.gradient import GradientEffect
from ledfx.effects.utils.corsair import CorsairEffect, ram_layout
from ledfx.effects.utils.custom import FloatArray

# Half the height of a car, as a share of a stick
CAR = 0.1
SHAFT = 0.03


class RamElevators(CorsairEffect, GradientEffect):
    NAME = "RAM Elevators"
    # Effect declares HIDDEN_KEYS = None, so every list override trips bad-override.
    HIDDEN_KEYS: ClassVar[list[str]] = ["gradient_roll"]  # pyrefly: ignore[bad-override]

    class Config(GradientEffect.Config):
        speed: CoercedFloat = Field(
            4.0, description="How quickly the cars reach their floor", ge=1.0, le=15.0
        )

    config = TypedConfig(Config)

    def on_activate(self, pixel_count: int) -> None:
        self._ram = ram_layout(pixel_count)
        sticks = self._ram.sticks
        # Where each car is, and the floor it is heading for, 0 at the bottom to 1 at the top
        self._cars: FloatArray = np.zeros(sticks)
        self._floors: FloatArray = np.zeros(sticks)

    @override
    def render(self) -> None:
        dt = self.step()
        ram = self._ram
        # On each beat one car is called to a new floor; a percussive hit calls another
        for called in (self.beat(), self.hit()):
            if called:
                car = self._rng.integers(ram.sticks)
                self._floors[car] = self._rng.random()
        self._cars += (self._floors - self._cars) * min(1.0, dt * self.config.speed)

        car = self._cars[ram.stick]
        inside = np.abs(ram.height - car) <= CAR + 0.06
        moving = np.minimum(1.0, np.abs(self._floors - self._cars) * 6)[ram.stick]
        colors = self.get_gradient_color_vectorized1d(np.clip(car, 0, 0.999))
        # A car glows brighter while it travels
        level = np.where(inside, 0.6 + 0.4 * moving, SHAFT)
        self.pixels = colors * level[:, None]
