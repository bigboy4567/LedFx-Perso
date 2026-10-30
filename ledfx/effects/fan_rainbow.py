from pydantic import Field
from typing_extensions import override

from ledfx.configuration.fields import CoercedFloat
from ledfx.configuration.plugin import TypedConfig
from ledfx.effects.utils.corsair import CorsairEffect, fan_layout, stack_height
from ledfx.effects.utils.custom import FloatArray, hue_colors


class FanRainbow(CorsairEffect):
    NAME = "Fan Rainbow"

    class Config(CorsairEffect.Config):
        repeats: CoercedFloat = Field(
            1.0, description="Rainbows up the stack of fans", ge=0.25, le=4.0
        )
        speed: CoercedFloat = Field(
            0.25,
            description="Rainbows rising past per beat of the song",
            ge=0.0,
            le=2.0,
        )

    config = TypedConfig(Config)

    def on_activate(self, pixel_count: int) -> None:
        self._height: FloatArray = stack_height(fan_layout(pixel_count))
        self.shift = 0.0

    @override
    def render(self) -> None:
        self.shift += self.song_moved() * self.config.speed + self.step() * 0.03
        # One rainbow standing up the whole stack, rising with the song
        hues = (self._height * self.config.repeats - self.shift) % 1
        self.pixels = hue_colors(hues) * (0.5 + 0.5 * self.loudness)
