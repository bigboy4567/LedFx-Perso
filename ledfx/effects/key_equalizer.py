from typing import ClassVar

import numpy as np
from pydantic import Field
from typing_extensions import override

from ledfx.configuration.fields import CoercedFloat, CoercedInt
from ledfx.configuration.plugin import TypedConfig
from ledfx.effects.audio import AudioAnalysisSource, AudioReactiveEffect
from ledfx.effects.gradient import GradientEffect
from ledfx.effects.utils.corsair import (
    BAR,
    CORSAIR_CATEGORY,
    G_KEY,
    KEY,
    LOGO,
    keyboard_layout,
)
from ledfx.effects.utils.custom import (
    BeatLatch,
    FloatArray,
    IntArray,
    frame_step,
    volume_of,
)

# Keys beyond the level glow this faintly, so the board stays readable
UNLIT = 0.04
WHITE = np.array((255.0, 255.0, 255.0))


class KeyEqualizer(AudioReactiveEffect, GradientEffect):
    NAME = "Key Equalizer"
    CATEGORY = CORSAIR_CATEGORY
    # Effect declares HIDDEN_KEYS = None, so every list override trips bad-override.
    HIDDEN_KEYS: ClassVar[list[str]] = ["gradient_roll"]  # pyrefly: ignore[bad-override]

    class Config(GradientEffect.Config):
        bands: CoercedInt = Field(
            16,
            description="Frequency bands across the keys, bass on the left",
            ge=4,
            le=32,
        )
        gain: CoercedFloat = Field(
            1.5, description="How high the music lifts the bands", ge=0.5, le=5.0
        )
        light_bar: bool = Field(True, description="The light bar shows the volume")

    config = TypedConfig(Config)

    def on_activate(self, pixel_count: int) -> None:
        board = keyboard_layout(pixel_count)
        self._zone: IntArray = board.zone
        keys = board.zone == KEY
        x, y = board.x, board.y
        # Key columns become bands, key rows the height of each band
        left, right = (x[keys].min(), x[keys].max()) if keys.any() else (0.0, 1.0)
        self._column: FloatArray = np.clip((x - left) / max(right - left, 1e-6), 0, 1)
        top, bottom = (y[keys].min(), y[keys].max()) if keys.any() else (0.0, 1.0)
        self._height: FloatArray = np.clip((bottom - y) / max(bottom - top, 1e-6), 0, 1)
        self._x: FloatArray = x
        g_keys = board.zone == G_KEY
        g_top, g_bottom = (
            (y[g_keys].min(), y[g_keys].max()) if g_keys.any() else (0.0, 1.0)
        )
        self._g_height: FloatArray = np.clip(
            (g_bottom - y) / max(g_bottom - g_top, 1e-6), 0, 1
        )
        self._bands: FloatArray = np.zeros(self.config.bands)
        self._volume = 0.0
        self._lows = 0.0
        self._flash = 0.0
        self._latch = BeatLatch()

    @override
    def audio_data_updated(self, data: AudioAnalysisSource) -> None:
        bands = self.melbank(filtered=True, size=self.config.bands)
        self._bands = np.clip(np.asarray(bands, dtype=float) * self.config.gain, 0, 1)
        self._volume = volume_of(data)
        self._lows = float(data.lows_power())
        self._latch.listen(data, "Beat")

    @override
    def render(self) -> None:
        self._flash *= float(np.exp(-frame_step(self.passed) * 6))
        if self._latch.take(self.now):
            self._flash = 1.0

        count = self._bands.size
        band = np.minimum((self._column * count).astype(int), count - 1)
        level = self._bands[band]
        lit = np.where(self._height <= level + 1e-9, 1.0, UNLIT)
        pixels = (
            self.get_gradient_color_vectorized1d(self._height * 0.999) * lit[:, None]
        )
        zone = self._zone
        # The G keys stack up with the bass, the light bar fills with the volume
        g_lit = np.where(self._g_height <= min(1.0, self._lows * 1.5), 1.0, UNLIT)
        pixels[zone == G_KEY] = (
            self.get_gradient_color_vectorized1d(self._g_height * 0.999)
            * g_lit[:, None]
        )[zone == G_KEY]
        if self.config.light_bar:
            bar_lit = np.where(self._x <= min(1.0, self._volume * 2), 1.0, UNLIT)
            bar = (
                self.get_gradient_color_vectorized1d(self._x * 0.999) * bar_lit[:, None]
            )
            pixels[zone == BAR] = bar[zone == BAR]
        # The logo flashes on the beat
        pixels[zone == LOGO] = WHITE * max(0.1, self._flash)
        self.pixels = np.clip(pixels, 0, 255)
