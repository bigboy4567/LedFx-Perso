from typing import ClassVar

import numpy as np
from pydantic import Field
from typing_extensions import override

from ledfx.configuration.fields import CoercedFloat
from ledfx.configuration.plugin import TypedConfig
from ledfx.effects.gradient import GradientEffect
from ledfx.effects.utils.corsair import CorsairEffect, aio_layout, breath


class PumpBreathe(CorsairEffect, GradientEffect):
    NAME = "Pump Breathe"
    # Effect declares HIDDEN_KEYS = None, so every list override trips bad-override.
    HIDDEN_KEYS: ClassVar[list[str]] = ["gradient_roll"]  # pyrefly: ignore[bad-override]

    class Config(GradientEffect.Config):
        beats_per_breath: CoercedFloat = Field(
            4.0, description="Beats of the song for one breath", ge=1.0, le=16.0
        )

    config = TypedConfig(Config)

    def on_activate(self, pixel_count: int) -> None:
        self._aio = aio_layout(pixel_count)
        self._breaths = 0.0

    @override
    def render(self) -> None:
        self._breaths += (
            self.song_moved() / self.config.beats_per_breath + self.step() * 0.03
        )
        aio = self._aio
        # The pump breathes in while the radiator breathes out, and the color drifts breath by breath
        pump = float(breath(self._breaths))
        level = np.where(aio.pump, pump, 1 - pump) * (0.6 + 0.4 * self.loudness)
        hue = (self._breaths * 0.1) % 1
        colors = self.get_gradient_color_vectorized1d(np.full(level.size, hue * 0.999))
        self.pixels = colors * (0.03 + 0.97 * level)[:, None]
