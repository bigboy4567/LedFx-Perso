from typing import ClassVar, Literal

import numpy as np
from pydantic import Field
from typing_extensions import override

from ledfx.configuration.plugin import TypedConfig
from ledfx.effects.gradient import GradientEffect
from ledfx.effects.utils.corsair import CorsairEffect, fan_layout

# Fans other than the lit one stay this dim
DIM = 0.06

Path = Literal["Down", "Up", "Bounce"]


class FanChase(CorsairEffect, GradientEffect):
    NAME = "Fan Chase"
    # Effect declares HIDDEN_KEYS = None, so every list override trips bad-override.
    HIDDEN_KEYS: ClassVar[list[str]] = ["gradient_roll"]  # pyrefly: ignore[bad-override]

    class Config(GradientEffect.Config):
        path: Path = Field(
            "Bounce",
            description="Which way the light jumps from fan to fan on each beat",
        )

    config = TypedConfig(Config)

    def on_activate(self, pixel_count: int) -> None:
        self._fans = fan_layout(pixel_count)
        self._jumps = 0
        self._glow = 1.0
        self._spin = 0.0

    def lit_fan(self) -> int:
        count = self._fans.count
        match self.config.path:
            case "Down":
                return self._jumps % count
            case "Up":
                return count - 1 - self._jumps % count
            case "Bounce":
                cycle = max(1, 2 * count - 2)
                place = self._jumps % cycle
                return place if place < count else cycle - place

    @override
    def render(self) -> None:
        dt = self.step()
        self._spin += dt * 0.5
        self._glow *= float(np.exp(-dt * 2))
        if self.beat():
            self._jumps += 1
            self._glow = 1.0

        fans = self._fans
        lit = fans.fan == self.lit_fan()
        colors = self.get_gradient_color_vectorized1d(
            (fans.angle + self._spin + self._jumps * 0.15) % 1
        )
        level = np.where(lit, 0.35 + 0.65 * self._glow, DIM)
        self.pixels = colors * level[:, None]
