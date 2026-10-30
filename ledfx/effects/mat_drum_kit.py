import numpy as np
from pydantic import Field
from typing_extensions import override

from ledfx.configuration.fields import CoercedFloat
from ledfx.configuration.plugin import TypedConfig
from ledfx.effects.audio import AudioAnalysisSource
from ledfx.effects.utils.corsair import CorsairEffect, DrumLatch, mat_height, mat_layout
from ledfx.effects.utils.custom import (
    HAT,
    KICK,
    SNARE,
    FloatArray,
    IntArray,
    color_array,
)

# The kick lights the bottom of the U and the mouse, the snare the left side, the hats the right
COLORS = np.array([color_array(color) for color in ("#FF2000", "#FFD000", "#00C0FF")])
UNLIT = 0.03


class MatDrumKit(CorsairEffect):
    NAME = "Mat Drum Kit"

    class Config(CorsairEffect.Config):
        decay: CoercedFloat = Field(
            5.0, description="How quickly a drum fades after a hit", ge=1.0, le=15.0
        )

    config = TypedConfig(Config)

    def on_activate(self, pixel_count: int) -> None:
        mat = mat_layout(pixel_count)
        bottom = mat_height(mat) < 0.35
        drum = np.where(bottom, KICK, np.where(mat.along < 0.5, SNARE, HAT))
        self._drum: IntArray = np.where(mat.mouse, KICK, drum)
        self.hits: FloatArray = np.zeros(3)
        self._drums = DrumLatch()

    @override
    def audio_data_updated(self, data: AudioAnalysisSource) -> None:
        super().audio_data_updated(data)
        self._drums.listen(data)

    @override
    def render(self) -> None:
        self.hits *= float(np.exp(-self.step() * self.config.decay))
        for drum in self._drums.take():
            self.hits[drum] = 1.0
        level = np.maximum(self.hits[self._drum], UNLIT)
        self.pixels = COLORS[self._drum] * level[:, None]
