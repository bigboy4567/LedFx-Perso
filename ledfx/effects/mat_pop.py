import numpy as np
from pydantic import Field
from typing_extensions import override

from ledfx.configuration.fields import CoercedFloat
from ledfx.configuration.plugin import TypedConfig
from ledfx.effects.utils.corsair import CorsairEffect, mat_layout
from ledfx.effects.utils.custom import hue_colors

WHITE = np.array((255.0, 255.0, 255.0))


class MatPop(CorsairEffect):
    NAME = "Mat Pop"

    class Config(CorsairEffect.Config):
        fade: CoercedFloat = Field(
            2.5, description="How quickly the pad fades after it pops", ge=0.5, le=10.0
        )

    config = TypedConfig(Config)

    def on_activate(self, pixel_count: int) -> None:
        self._mouse = mat_layout(pixel_count).mouse
        self.hue = 0.0
        self._glow = 0.0
        self._mouse_glow = 0.0

    @override
    def render(self) -> None:
        fade = float(np.exp(-self.step() * self.config.fade))
        self._glow *= fade
        self._mouse_glow *= fade
        # Each beat the pad pops into a new color, never the one it had
        if self.beat():
            self.hue = (self.hue + 0.2 + self._rng.random() * 0.6) % 1
            self._glow = 1.0
        # Each percussive hit pops the mouse white
        if self.hit():
            self._mouse_glow = 1.0
        size = self._mouse.size
        pad = hue_colors(np.full(size, self.hue)) * self._glow
        mouse = np.maximum(pad, WHITE * self._mouse_glow)
        self.pixels = np.where(self._mouse[:, None], mouse, pad)
