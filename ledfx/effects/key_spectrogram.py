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

# Moments of the song across the board
COLUMNS = 24


class KeySpectrogram(CorsairEffect, GradientEffect):
    NAME = "Key Spectrogram"
    # Effect declares HIDDEN_KEYS = None, so every list override trips bad-override.
    HIDDEN_KEYS: ClassVar[list[str]] = ["gradient_roll"]  # pyrefly: ignore[bad-override]

    class Config(GradientEffect.Config):
        gain: CoercedFloat = Field(
            1.5, description="How brightly the music lights the bands", ge=0.5, le=5.0
        )
        columns_per_second: CoercedFloat = Field(
            10.0,
            description="How quickly the music scrolls across the board",
            ge=2.0,
            le=40.0,
        )

    config = TypedConfig(Config)

    def on_activate(self, pixel_count: int) -> None:
        board = keyboard_layout(pixel_count)
        rows, count = keyboard_rows(board)
        # The bass along the front row, the treble along the light bar
        self._band: IntArray = count - 1 - rows
        self._column: IntArray = np.minimum(
            (board.x * COLUMNS).astype(int), COLUMNS - 1
        )
        # What each column showed, the newest on the right
        self._history: FloatArray = np.zeros((COLUMNS, count))
        self._bands: FloatArray = np.zeros(count)
        self._due = 0.0

    @override
    def audio_data_updated(self, data: AudioAnalysisSource) -> None:
        super().audio_data_updated(data)
        bands = self.melbank(filtered=True, size=self._bands.size)
        self._bands = np.clip(np.asarray(bands, dtype=float) * self.config.gain, 0, 1)

    @override
    def render(self) -> None:
        self._due += self.step() * self.config.columns_per_second
        history = self._history
        steps = min(int(self._due), COLUMNS)
        self._due -= int(self._due)
        if steps:
            history[:-steps] = history[steps:].copy()
            history[-steps:] = self._bands
        history[-1] = self._bands
        value = history[self._column, self._band]
        colors = self.get_gradient_color_vectorized1d(value * 0.999)
        self.pixels = colors * np.maximum(value, 0.02)[:, None]
