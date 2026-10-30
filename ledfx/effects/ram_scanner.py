from typing import ClassVar

import numpy as np
from pydantic import Field
from typing_extensions import override

from ledfx.configuration.fields import CoercedFloat
from ledfx.configuration.plugin import TypedConfig
from ledfx.effects.gradient import GradientEffect
from ledfx.effects.utils.corsair import CorsairEffect, ram_layout

# The beam leaves a fading trail this long behind it, as a share of a stick
TRAIL = 0.35


class RamScanner(CorsairEffect, GradientEffect):
    NAME = "RAM Scanner"
    # Effect declares HIDDEN_KEYS = None, so every list override trips bad-override.
    HIDDEN_KEYS: ClassVar[list[str]] = ["gradient_roll"]  # pyrefly: ignore[bad-override]

    class Config(GradientEffect.Config):
        beats_per_sweep: CoercedFloat = Field(
            1.0,
            description="Beats of the song for the beam to go up or down once",
            ge=0.25,
            le=4.0,
        )
        stagger: CoercedFloat = Field(
            0.15,
            description="How far behind its left neighbour each stick's beam runs, as a share of a sweep",
            ge=0.0,
            le=0.5,
        )

    config = TypedConfig(Config)

    def on_activate(self, pixel_count: int) -> None:
        self._ram = ram_layout(pixel_count)
        self._sweeps = 0.0

    @override
    def render(self) -> None:
        self._sweeps += (
            self.song_moved() / self.config.beats_per_sweep + self.step() * 0.05
        )
        ram = self._ram
        # Up then down then up again, each stick a little behind the one on its left
        sweeps = self._sweeps - ram.stick * self.config.stagger
        going_up = np.floor(sweeps) % 2 == 0
        within = sweeps % 1
        beam = np.where(going_up, within, 1 - within)
        behind = np.where(going_up, beam - ram.height, ram.height - beam)
        level = np.where(
            (behind >= -0.06) & (behind < TRAIL),
            1 - np.clip(behind, 0, TRAIL) / TRAIL,
            0.0,
        )
        colors = self.get_gradient_color_vectorized1d(np.clip(ram.height, 0, 0.999))
        self.pixels = colors * (0.03 + 0.97 * level**1.5)[:, None]
