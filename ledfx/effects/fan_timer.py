from typing import ClassVar

import numpy as np
from pydantic import Field
from typing_extensions import override

from ledfx.configuration.fields import CoercedFloat
from ledfx.configuration.plugin import TypedConfig
from ledfx.effects.gradient import GradientEffect
from ledfx.effects.utils.corsair import FAN_HUB, CorsairEffect, fan_layout

SPENT = 0.03
FLASH = 5.0
WHITE = np.array((255.0, 255.0, 255.0))


class FanTimer(CorsairEffect, GradientEffect):
    NAME = "Fan Timer"
    # Effect declares HIDDEN_KEYS = None, so every list override trips bad-override.
    HIDDEN_KEYS: ClassVar[list[str]] = ["gradient_roll"]  # pyrefly: ignore[bad-override]

    class Config(GradientEffect.Config):
        beats_per_fan: CoercedFloat = Field(
            4.0,
            description="Beats of the song each fan takes to run down",
            ge=1.0,
            le=16.0,
        )

    config = TypedConfig(Config)

    def on_activate(self, pixel_count: int) -> None:
        self._fans = fan_layout(pixel_count)
        self._current = -1
        self._flash = 0.0

    @override
    def render(self) -> None:
        self._flash *= float(np.exp(-self.step() * FLASH))
        fans = self._fans
        # The fans run down one after the other, from the top, then all fill up again
        spent = self.song.beats / self.config.beats_per_fan
        current = int(spent) % fans.count
        left = 1 - spent % 1
        if current != self._current:
            self._current = current
            self._flash = 1.0
        # The running fan's rim empties clockwise from the top
        running = np.where(fans.angle < left, 1.0, SPENT)
        rim = np.where(
            fans.fan == current, running, np.where(fans.fan > current, 1.0, SPENT)
        )
        reading = np.where(
            fans.fan == current, left, np.where(fans.fan > current, 1.0, 0.0)
        )
        colors = self.get_gradient_color_vectorized1d(np.clip(reading, 0, 1) * 0.999)
        pixels = colors * rim[:, None]
        # The hub of the fan that starts running flashes
        hub = np.where(
            (fans.fan == current)[:, None], WHITE * max(0.1, self._flash), colors * 0.05
        )
        self.pixels = np.where((fans.ring == FAN_HUB)[:, None], hub, pixels)
