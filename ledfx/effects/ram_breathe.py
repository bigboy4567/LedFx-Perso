from typing import ClassVar

from pydantic import Field
from typing_extensions import override

from ledfx.configuration.fields import CoercedFloat
from ledfx.configuration.plugin import TypedConfig
from ledfx.effects.gradient import GradientEffect
from ledfx.effects.utils.corsair import CorsairEffect, breath, ram_layout


class RamBreathe(CorsairEffect, GradientEffect):
    NAME = "RAM Breathe"
    # Effect declares HIDDEN_KEYS = None, so every list override trips bad-override.
    HIDDEN_KEYS: ClassVar[list[str]] = ["gradient_roll"]  # pyrefly: ignore[bad-override]

    class Config(GradientEffect.Config):
        beats_per_breath: CoercedFloat = Field(
            4.0, description="Beats of the song for one breath", ge=1.0, le=16.0
        )
        spread: CoercedFloat = Field(
            0.15,
            description="How far behind its left neighbour each stick breathes, as a share of a breath",
            ge=0.0,
            le=0.5,
        )

    config = TypedConfig(Config)

    def on_activate(self, pixel_count: int) -> None:
        self._ram = ram_layout(pixel_count)
        self._breaths = 0.0

    @override
    def render(self) -> None:
        self._breaths += (
            self.song_moved() / self.config.beats_per_breath + self.step() * 0.03
        )
        ram = self._ram
        # The breath runs across the sticks, filling each from the bottom
        full = breath(self._breaths - ram.stick * self.config.spread)
        level = (
            (0.3 + 0.7 * full)
            * (1 - ram.height * (1 - full))
            * (0.6 + 0.4 * self.loudness)
        )
        colors = self.get_gradient_color_vectorized1d(
            ram.stick / max(ram.sticks - 1, 1) * 0.999
        )
        self.pixels = colors * (0.03 + 0.97 * level)[:, None]
