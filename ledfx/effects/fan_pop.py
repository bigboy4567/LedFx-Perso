import numpy as np
from pydantic import Field
from typing_extensions import override

from ledfx.configuration.fields import CoercedFloat
from ledfx.configuration.plugin import TypedConfig
from ledfx.effects.utils.corsair import FAN_HUB, CorsairEffect, fan_layout
from ledfx.effects.utils.custom import FloatArray, hue_colors

WHITE = np.array((255.0, 255.0, 255.0))


class FanPop(CorsairEffect):
    NAME = "Fan Pop"

    class Config(CorsairEffect.Config):
        fade: CoercedFloat = Field(
            2.5, description="How quickly a fan fades after it pops", ge=0.5, le=10.0
        )

    config = TypedConfig(Config)

    def on_activate(self, pixel_count: int) -> None:
        self._fans = fan_layout(pixel_count)
        count = self._fans.count
        self._glow: FloatArray = np.zeros(count)
        self._hues: FloatArray = np.zeros(count)
        self._hubs = 0.0

    @override
    def render(self) -> None:
        fade = float(np.exp(-self.step() * self.config.fade))
        self._glow *= fade
        self._hubs *= fade
        fans = self._fans
        # Each beat a fan pops into a new color, never the one it had
        if self.beat():
            fan = int(self._rng.integers(fans.count))
            self._hues[fan] = (self._hues[fan] + 0.2 + self._rng.random() * 0.6) % 1
            self._glow[fan] = 1.0
        # Each percussive hit pops every hub white
        if self.hit():
            self._hubs = 1.0
        rim = hue_colors(self._hues[fans.fan]) * self._glow[fans.fan][:, None]
        hub = np.maximum(rim, WHITE * self._hubs)
        self.pixels = np.where((fans.ring == FAN_HUB)[:, None], hub, rim)
