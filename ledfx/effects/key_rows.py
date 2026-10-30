from typing import ClassVar

import numpy as np
from pydantic import Field
from typing_extensions import override

from ledfx.configuration.fields import CoercedFloat
from ledfx.configuration.plugin import TypedConfig
from ledfx.effects.audio import AudioAnalysisSource
from ledfx.effects.gradient import GradientEffect
from ledfx.effects.utils.corsair import CorsairEffect, keyboard_layout, keyboard_rows
from ledfx.effects.utils.custom import FloatArray, IntArray

UNLIT = 0.03


class KeyRows(CorsairEffect, GradientEffect):
    NAME = "Key Rows"
    # Effect declares HIDDEN_KEYS = None, so every list override trips bad-override.
    HIDDEN_KEYS: ClassVar[list[str]] = ["gradient_roll"]  # pyrefly: ignore[bad-override]

    class Config(GradientEffect.Config):
        gain: CoercedFloat = Field(
            1.5, description="How far the music stretches the rows", ge=0.5, le=5.0
        )
        centered: bool = Field(
            False,
            description="The rows grow out from the middle instead of from the left",
        )

    config = TypedConfig(Config)

    def on_activate(self, pixel_count: int) -> None:
        board = keyboard_layout(pixel_count)
        self._x: FloatArray = board.x
        rows, count = keyboard_rows(board)
        # The front row is the bass, the light bar at the back the treble
        self._band: IntArray = count - 1 - rows
        self._bands: FloatArray = np.zeros(count)
        self._shown: FloatArray = np.zeros(count)

    @override
    def audio_data_updated(self, data: AudioAnalysisSource) -> None:
        super().audio_data_updated(data)
        bands = self.melbank(filtered=True, size=self._bands.size)
        self._bands = np.clip(np.asarray(bands, dtype=float) * self.config.gain, 0, 1)

    @override
    def render(self) -> None:
        self._shown += (self._bands - self._shown) * min(1.0, self.step() * 15)
        reach = np.abs(self._x - 0.5) * 2 if self.config.centered else self._x
        lit = reach <= self._shown[self._band] + 0.02
        count = max(self._bands.size - 1, 1)
        colors = self.get_gradient_color_vectorized1d(self._band / count * 0.999)
        self.pixels = colors * np.where(lit, 1.0, UNLIT)[:, None]
