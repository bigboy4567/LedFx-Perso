from typing import ClassVar

import numpy as np
from pydantic import Field
from typing_extensions import override

from ledfx.configuration.fields import CoercedFloat, CoercedInt
from ledfx.configuration.plugin import TypedConfig
from ledfx.effects.gradient import GradientEffect
from ledfx.effects.utils.corsair import CorsairEffect, aio_layout
from ledfx.effects.utils.custom import FloatArray


class PumpMandala(CorsairEffect, GradientEffect):
    NAME = "Pump Mandala"
    # Effect declares HIDDEN_KEYS = None, so every list override trips bad-override.
    HIDDEN_KEYS: ClassVar[list[str]] = ["gradient_roll"]  # pyrefly: ignore[bad-override]

    class Config(GradientEffect.Config):
        folds: CoercedInt = Field(
            4, description="Times the pattern repeats round the ring", ge=2, le=8
        )
        turns_per_beat: CoercedFloat = Field(
            0.125,
            description="Turns of the pattern per beat of the song",
            ge=0.02,
            le=1.0,
        )

    config = TypedConfig(Config)

    def on_activate(self, pixel_count: int) -> None:
        self._aio = aio_layout(pixel_count)
        self._turn = 0.0
        self._heading = 1.0

    def pattern(self, place: FloatArray) -> tuple[FloatArray, FloatArray]:
        """How bright each place is, and its color along the gradient; one fold per unit."""
        turn = self._turn
        outer = 0.5 + 0.5 * np.cos(2 * np.pi * (place + turn))
        inner = 0.5 + 0.5 * np.cos(2 * np.pi * (place * 2 - turn * 1.5))
        return outer, (outer * 0.5 + inner * 0.5 + turn * 0.1) % 1

    @override
    def render(self) -> None:
        # On the first beat of each bar the pattern turns back the other way
        if self.beat() and int(self.song.beats) % 4 == 0:
            self._heading = -self._heading
        moved = self.song_moved() * self.config.turns_per_beat + self.step() * 0.02
        self._turn += moved * self._heading
        aio = self._aio
        # The pump shows the whole pattern, each radiator fan one fold of it
        outer, hue = self.pattern(aio.angle * np.where(aio.pump, self.config.folds, 1))
        colors = self.get_gradient_color_vectorized1d(hue * 0.999)
        level = 0.3 + 0.7 * outer * (0.5 + 0.5 * self.loudness)
        self.pixels = colors * level[:, None]
