from typing import ClassVar

import numpy as np
from pydantic import Field
from typing_extensions import override

from ledfx.configuration.fields import CoercedFloat
from ledfx.configuration.plugin import TypedConfig
from ledfx.effects.audio import AudioAnalysisSource
from ledfx.effects.gradient import GradientEffect
from ledfx.effects.utils.corsair import KEYBOARD_DEPTH, CorsairEffect, keyboard_layout
from ledfx.effects.utils.custom import FloatArray, IntArray

BANDS = 10


class KeyRadialEq(CorsairEffect, GradientEffect):
    NAME = "Key Radial EQ"
    # Effect declares HIDDEN_KEYS = None, so every list override trips bad-override.
    HIDDEN_KEYS: ClassVar[list[str]] = ["gradient_roll"]  # pyrefly: ignore[bad-override]

    class Config(GradientEffect.Config):
        gain: CoercedFloat = Field(
            1.5, description="How brightly the music lights the rings", ge=0.5, le=5.0
        )

    config = TypedConfig(Config)

    def on_activate(self, pixel_count: int) -> None:
        board = keyboard_layout(pixel_count)
        # Rings out from the middle of the board: the bass in the middle, the treble at the edges
        distance = np.hypot(board.x - 0.5, (board.y - 0.5) * KEYBOARD_DEPTH)
        reach = max(float(distance.max()), 1e-6)
        self._band: IntArray = np.minimum(
            (distance / reach * BANDS).astype(int), BANDS - 1
        )
        self._bands: FloatArray = np.zeros(BANDS)
        self._shown: FloatArray = np.zeros(BANDS)

    @override
    def audio_data_updated(self, data: AudioAnalysisSource) -> None:
        super().audio_data_updated(data)
        bands = self.melbank(filtered=True, size=BANDS)
        self._bands = np.clip(np.asarray(bands, dtype=float) * self.config.gain, 0, 1)

    @override
    def render(self) -> None:
        self._shown += (self._bands - self._shown) * min(1.0, self.step() * 15)
        colors = self.get_gradient_color_vectorized1d(self._band / (BANDS - 1) * 0.999)
        self.pixels = colors * (0.03 + 0.97 * self._shown[self._band])[:, None]
