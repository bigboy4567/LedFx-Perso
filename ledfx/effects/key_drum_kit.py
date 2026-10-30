import numpy as np
from pydantic import Field
from typing_extensions import override

from ledfx.configuration.fields import CoercedFloat
from ledfx.configuration.plugin import TypedConfig
from ledfx.effects.audio import AudioAnalysisSource
from ledfx.effects.utils.corsair import (
    BAR,
    LOGO,
    CorsairEffect,
    DrumLatch,
    keyboard_layout,
)
from ledfx.effects.utils.custom import (
    HAT,
    KICK,
    SNARE,
    FloatArray,
    IntArray,
    color_array,
)

# The front rows answer the kick, the middle rows the snare, the top rows and light bar the hats
COLORS = np.array([color_array(color) for color in ("#FF2000", "#FFD000", "#00C0FF")])
UNLIT = 0.03
WHITE = np.array((255.0, 255.0, 255.0))


class KeyDrumKit(CorsairEffect):
    NAME = "Key Drum Kit"

    class Config(CorsairEffect.Config):
        decay: CoercedFloat = Field(
            5.0,
            description="How quickly a drum's keys fade after a hit",
            ge=1.0,
            le=15.0,
        )

    config = TypedConfig(Config)

    def on_activate(self, pixel_count: int) -> None:
        board = keyboard_layout(pixel_count)
        drum = np.where(board.y > 0.8, KICK, np.where(board.y > 0.5, SNARE, HAT))
        self._drum: IntArray = np.where(board.zone == BAR, HAT, drum)
        self._logo = board.zone == LOGO
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
        pixels = COLORS[self._drum] * level[:, None]
        # The logo flashes with any drum
        self.pixels = np.where(
            self._logo[:, None], WHITE * max(UNLIT, float(self.hits.max())), pixels
        )
