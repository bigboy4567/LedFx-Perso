from typing import ClassVar

import numpy as np
from pydantic import Field
from typing_extensions import override

from ledfx.configuration.fields import CoercedFloat, CoercedInt
from ledfx.configuration.plugin import TypedConfig
from ledfx.effects.gradient import GradientEffect
from ledfx.effects.utils.corsair import FAN_HUB, CorsairEffect, fan_layout

WHITE = np.array((255.0, 255.0, 255.0))


class FanPinwheel(CorsairEffect, GradientEffect):
    NAME = "Fan Pinwheel"
    # Effect declares HIDDEN_KEYS = None, so every list override trips bad-override.
    HIDDEN_KEYS: ClassVar[list[str]] = ["gradient_roll"]  # pyrefly: ignore[bad-override]

    class Config(GradientEffect.Config):
        slices: CoercedInt = Field(
            4, description="Colored slices on each rim", ge=2, le=12
        )
        drift: CoercedFloat = Field(
            0.1,
            description="How fast the pinwheel turns on its own, in turns per second",
            ge=0.0,
            le=1.0,
        )

    config = TypedConfig(Config)

    def on_activate(self, pixel_count: int) -> None:
        self._fans = fan_layout(pixel_count)
        self._turn = 0.0
        self._kick = 0.0
        self._flash = 0.0

    @override
    def render(self) -> None:
        dt = self.step()
        slices = self.config.slices
        if self.beat():
            # Each beat snaps the pinwheel round by one slice
            self._kick += 1 / slices
            self._flash = 1.0
        eased = self._kick * min(1.0, dt * 12)
        self._kick -= eased
        self._turn += eased + dt * self.config.drift
        self._flash *= float(np.exp(-dt * 6))

        fans = self._fans
        # Neighbouring fans turn opposite ways, like meshed gears
        heading = np.where(fans.fan % 2 == 0, 1.0, -1.0)
        place = (fans.angle - self._turn * heading) % 1
        slice_index = np.floor(place * slices)
        colors = self.get_gradient_color_vectorized1d(slice_index / slices)
        hub = (fans.ring == FAN_HUB)[:, None]
        hub_color = WHITE * (0.15 + 0.85 * self._flash)
        self.pixels = np.where(hub, hub_color, colors * (0.5 + 0.5 * self.loudness))
