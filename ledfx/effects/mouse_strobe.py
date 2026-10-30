import numpy as np
from pydantic import Field
from typing_extensions import override

from ledfx.configuration.fields import CoercedFloat, Color
from ledfx.configuration.plugin import TypedConfig
from ledfx.effects.utils.corsair import CorsairEffect, mat_layout
from ledfx.effects.utils.custom import color_array


class MouseStrobe(CorsairEffect):
    NAME = "Mouse Strobe"

    class Config(CorsairEffect.Config):
        flash_color: Color = Field(
            "#FFFFFF", description="Color of the mouse's flashes"
        )
        glow_color: Color = Field("#4000FF", description="Color of the pad's glow")
        decay: CoercedFloat = Field(
            20.0, description="How quickly a flash dies", ge=4.0, le=40.0
        )

    config = TypedConfig(Config)

    def on_activate(self, pixel_count: int) -> None:
        self._mouse = mat_layout(pixel_count).mouse
        self.flash = 0.0

    @override
    def config_updated(self, config: object) -> None:
        self._flash_color = color_array(self.config.flash_color)
        self._glow = color_array(self.config.glow_color)

    @override
    def render(self) -> None:
        self.flash *= float(np.exp(-self.step() * self.config.decay))
        # The mouse strobes on every percussive hit and every beat
        hit, beat = self.hit(), self.beat()
        if hit or beat:
            self.flash = 1.0
        # The pad glows softly with the bass beneath it
        pad = self._glow * (0.05 + 0.35 * self.levels[0])
        mouse = self._flash_color * self.flash
        self.pixels = np.where(self._mouse[:, None], mouse, pad)
