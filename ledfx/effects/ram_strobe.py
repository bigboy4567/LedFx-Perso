from typing import Literal

import numpy as np
from pydantic import Field
from typing_extensions import override

from ledfx.configuration.fields import Color
from ledfx.configuration.plugin import TypedConfig
from ledfx.effects.utils.corsair import CorsairEffect, ram_layout
from ledfx.effects.utils.custom import FloatArray, color_array

Order = Literal["Left to right", "Ping pong", "Random"]
# How quickly a flash dies
FLASH = 18.0


class RamStrobe(CorsairEffect):
    NAME = "RAM Strobe"

    class Config(CorsairEffect.Config):
        color: Color = Field("#FFFFFF", description="Color of the flashes")
        order: Order = Field(
            "Ping pong", description="Which stick flashes on each beat"
        )

    config = TypedConfig(Config)

    def on_activate(self, pixel_count: int) -> None:
        self._ram = ram_layout(pixel_count)
        self._flash: FloatArray = np.zeros(self._ram.sticks)
        self._flashes = 0

    @override
    def config_updated(self, config: object) -> None:
        self._color = color_array(self.config.color)

    def _next_stick(self) -> int:
        sticks = self._ram.sticks
        self._flashes += 1
        match self.config.order:
            case "Left to right":
                return self._flashes % sticks
            case "Ping pong":
                cycle = max(1, 2 * sticks - 2)
                place = self._flashes % cycle
                return place if place < sticks else cycle - place
            case _:
                return int(self._rng.integers(sticks))

    @override
    def render(self) -> None:
        dt = self.step()
        self._flash *= float(np.exp(-dt * FLASH))
        if self.beat():
            self._flash[self._next_stick()] = 1.0
        # Each percussive hit flashes every stick, a little dimmer
        if self.hit():
            self._flash = np.maximum(self._flash, 0.6)
        self.pixels = self._color * self._flash[self._ram.stick][:, None]
