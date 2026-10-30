import numpy as np
from pydantic import Field
from typing_extensions import override

from ledfx.configuration.fields import CoercedFloat, Color
from ledfx.configuration.plugin import TypedConfig
from ledfx.effects.utils.corsair import CorsairEffect, aio_layout
from ledfx.effects.utils.custom import color_array


class PumpStrobe(CorsairEffect):
    NAME = "Pump Strobe"

    class Config(CorsairEffect.Config):
        color: Color = Field("#FFFFFF", description="Color of the flashes")
        decay: CoercedFloat = Field(
            18.0, description="How quickly a flash dies", ge=4.0, le=40.0
        )

    config = TypedConfig(Config)

    def on_activate(self, pixel_count: int) -> None:
        self._aio = aio_layout(pixel_count)
        self.pump = 0.0
        self.fans = 0.0

    @override
    def config_updated(self, config: object) -> None:
        self._color = color_array(self.config.color)

    @override
    def render(self) -> None:
        fade = float(np.exp(-self.step() * self.config.decay))
        self.pump *= fade
        self.fans *= fade
        # The pump flashes on the bass beat, the radiator on every percussive hit
        if self.beat():
            self.pump = 1.0
        if self.hit():
            self.fans = 1.0
        level = np.where(self._aio.pump, self.pump, self.fans)
        self.pixels = self._color * level[:, None]
