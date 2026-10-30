import numpy as np
from pydantic import Field
from typing_extensions import override

from ledfx.configuration.fields import CoercedFloat, Color
from ledfx.configuration.plugin import TypedConfig
from ledfx.effects.utils.corsair import FAN_HUB, CorsairEffect, fan_layout
from ledfx.effects.utils.custom import color_array


class FanYinYang(CorsairEffect):
    NAME = "Fan Yin Yang"

    class Config(CorsairEffect.Config):
        yin_color: Color = Field("#FFFFFF", description="Color of one half")
        yang_color: Color = Field("#0030FF", description="Color of the other half")
        turns_per_bar: CoercedFloat = Field(
            0.5, description="Turns per bar of the song", ge=0.1, le=2.0
        )

    config = TypedConfig(Config)

    def on_activate(self, pixel_count: int) -> None:
        self._fans = fan_layout(pixel_count)
        self._turn = 0.0

    @override
    def config_updated(self, config: object) -> None:
        self._yin = color_array(self.config.yin_color)
        self._yang = color_array(self.config.yang_color)

    @override
    def render(self) -> None:
        self._turn += (
            self.song_moved() / 4 * self.config.turns_per_bar + self.step() * 0.03
        )
        fans = self._fans
        # Neighbouring fans turn opposite ways
        heading = np.where(fans.fan % 2 == 0, 1.0, -1.0)
        yin = ((fans.angle - self._turn * heading) % 1) < 0.5
        # The hub is each half's eye, in the other half's color
        yin = np.where(fans.ring == FAN_HUB, ~yin, yin)
        colors = np.where(yin[:, None], self._yin, self._yang)
        self.pixels = colors * (0.4 + 0.6 * self.loudness)
