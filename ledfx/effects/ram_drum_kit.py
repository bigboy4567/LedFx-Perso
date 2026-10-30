import numpy as np
from pydantic import Field
from typing_extensions import override

from ledfx.configuration.fields import CoercedFloat
from ledfx.configuration.plugin import TypedConfig
from ledfx.effects.audio import AudioAnalysisSource
from ledfx.effects.utils.corsair import CorsairEffect, DrumLatch, ram_layout
from ledfx.effects.utils.custom import (
    HAT,
    KICK,
    SNARE,
    FloatArray,
    IntArray,
    color_array,
)

# The colors of the kick, snare, hats and the volume stick
COLORS = np.array(
    [color_array(color) for color in ("#FF2000", "#FFD000", "#00C0FF", "#B040FF")]
)
UNLIT = 0.03


class RamDrumKit(CorsairEffect):
    NAME = "RAM Drum Kit"

    class Config(CorsairEffect.Config):
        decay: CoercedFloat = Field(
            4.0,
            description="How quickly a drum's stick drains after a hit",
            ge=1.0,
            le=12.0,
        )

    config = TypedConfig(Config)

    def on_activate(self, pixel_count: int) -> None:
        ram = ram_layout(pixel_count)
        self._ram = ram
        # The kick on the first stick, the snare on the second, the hats on the third,
        # and the last stick shows the volume
        self._part: IntArray = np.minimum(ram.stick * 4 // max(ram.sticks, 1), 3)
        self.hits: FloatArray = np.zeros(4)
        self._drums = DrumLatch()

    @override
    def audio_data_updated(self, data: AudioAnalysisSource) -> None:
        super().audio_data_updated(data)
        self._drums.listen(data)

    @override
    def render(self) -> None:
        self.hits *= float(np.exp(-self.step() * self.config.decay))
        for drum in self._drums.take():
            self.hits[{KICK: 0, SNARE: 1, HAT: 2}[drum]] = 1.0
        self.hits[3] = self.loudness
        ram = self._ram
        # Each hit fills its stick, which drains from the top
        level = self.hits[self._part]
        lit = (ram.height <= level + 1e-9) & (level > 0.02)
        self.pixels = COLORS[self._part] * np.where(lit, 1.0, UNLIT)[:, None]
