import numpy as np
from pydantic import Field
from typing_extensions import override

from ledfx.configuration.fields import CoercedFloat
from ledfx.configuration.plugin import TypedConfig
from ledfx.effects.audio import AudioAnalysisSource, AudioReactiveEffect
from ledfx.effects.utils.corsair import CORSAIR_CATEGORY, mat_layout
from ledfx.effects.utils.custom import (
    FloatArray,
    color_array,
    frame_step,
    volume_of,
)

GREEN = color_array("#00FF40")
YELLOW = color_array("#FFD000")
RED = color_array("#FF1000")
UNLIT = 0.04
# An LED lights once the level is within this of it, so a full meter lights the tips
REACH = 0.02
PEAK_FALL = 0.4


class MatMeter(AudioReactiveEffect):
    NAME = "Mat Meter"
    CATEGORY = CORSAIR_CATEGORY

    class Config(AudioReactiveEffect.Config):
        sensitivity: CoercedFloat = Field(
            1.8, description="How far the music fills the pad's edge", ge=0.5, le=4.0
        )

    config = TypedConfig(Config)

    def on_activate(self, pixel_count: int) -> None:
        mat = mat_layout(pixel_count)
        self._mouse = mat.mouse
        # The meter rises from the middle of the bottom edge up both sides
        self._height: FloatArray = np.abs(mat.along - 0.5) * 2
        self.level = 0.0
        self._peak = 0.0
        self._volume = 0.0

    @override
    def audio_data_updated(self, data: AudioAnalysisSource) -> None:
        self._volume = volume_of(data)

    def _scale(self, height: FloatArray) -> FloatArray:
        low = np.clip(height / 0.6, 0, 1)[..., None]
        high = np.clip((height - 0.6) / 0.4, 0, 1)[..., None]
        return GREEN + (YELLOW - GREEN) * low + (RED - YELLOW) * high

    @override
    def render(self) -> None:
        dt = frame_step(self.passed)
        target = min(1.0, self._volume * self.config.sensitivity)
        self.level += (target - self.level) * min(1.0, dt * 15)
        self._peak = max(self.level, self._peak - PEAK_FALL * dt)

        lit = np.where(self._height <= self.level + REACH, 1.0, UNLIT)
        pixels = self._scale(self._height) * lit[:, None]
        # The mouse glows the color of the recent peak
        if self._mouse.any():
            pixels[self._mouse] = self._scale(np.array([self._peak]))[0]
        self.pixels = pixels
