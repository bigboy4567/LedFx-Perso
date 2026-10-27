import numpy as np
from pydantic import Field
from typing_extensions import override

from ledfx.configuration.fields import CoercedFloat, Color
from ledfx.configuration.plugin import TypedConfig
from ledfx.effects.audio import AudioAnalysisSource, AudioReactiveEffect
from ledfx.effects.utils.custom import (
    CUSTOM_CATEGORY,
    BeatLatch,
    FloatArray,
    color_array,
    frame_step,
    volume_of,
)

# Bass and treble are compared to their own recent peaks, which fade this fast,
# so a song with quiet highs still gets a fair fight
PEAK_FADE = 0.3
PEAK_FLOOR = 0.05
# How far a beat shoves the front toward the treble side
BEAT_SHOVE = 0.08
# Darkest a side gets when its band is silent
MIN_SIDE = 0.25


class TugOfWar(AudioReactiveEffect):
    NAME = "Tug of War"
    CATEGORY = CUSTOM_CATEGORY

    class Config(AudioReactiveEffect.Config):
        bass_color: Color = Field("#FF2000", description="Color of the bass side")
        treble_color: Color = Field("#00A0FF", description="Color of the treble side")
        sensitivity: CoercedFloat = Field(
            1.5, description="How far the music pushes the front", ge=0.5, le=3.0
        )
        responsiveness: CoercedFloat = Field(
            6.0, description="How quickly the front follows the music", ge=1.0, le=20.0
        )
        spark: bool = Field(True, description="Glow white where the two sides meet")

    config = TypedConfig(Config)

    def on_activate(self, pixel_count: int) -> None:
        self._x: FloatArray = np.arange(pixel_count, dtype=float)
        self._front = 0.5
        self._lows = 0.0
        self._highs = 0.0
        self._volume = 0.0
        self._peaks: FloatArray = np.full(2, PEAK_FLOOR)
        self._latch = BeatLatch()

    @override
    def config_updated(self, config: object) -> None:
        self._bass = color_array(self.config.bass_color)
        self._treble = color_array(self.config.treble_color)

    @override
    def audio_data_updated(self, data: AudioAnalysisSource) -> None:
        self._lows = float(data.lows_power())
        self._highs = float(data.high_power())
        self._volume = volume_of(data)
        self._latch.listen(data, "Beat")

    @override
    def render(self) -> None:
        n = self.pixel_count
        dt = frame_step(self.passed)
        bands = np.array((self._lows, self._highs))
        self._peaks = np.maximum(
            bands, np.maximum(self._peaks * float(np.exp(-dt * PEAK_FADE)), PEAK_FLOOR)
        )
        lows, highs = bands / self._peaks
        target = 0.5 + (lows - highs) * 0.25 * self.config.sensitivity
        if self._latch.take(self.now):
            self._front += BEAT_SHOVE
        # Ease toward the target, frame rate independent
        self._front += (target - self._front) * (
            1 - np.exp(-dt * self.config.responsiveness)
        )
        self._front = float(np.clip(self._front, 0.05, 0.95))

        edge = self._front * n
        softness = max(1.0, n * 0.02)
        # 1 on the bass side, 0 on the treble side, a short blend at the front
        bass_share = 1 / (1 + np.exp((self._x - edge) / softness))
        bass = self._bass * (MIN_SIDE + (1 - MIN_SIDE) * lows)
        treble = self._treble * (MIN_SIDE + (1 - MIN_SIDE) * highs)
        pixels = bass * bass_share[:, None] + treble * (1 - bass_share[:, None])
        if self.config.spark:
            spark = np.exp(-(((self._x - edge) / softness) ** 2)) * min(
                1.0, self._volume * 2
            )
            pixels += (255 - pixels) * spark[:, None]
        self.pixels = np.clip(pixels, 0, 255)
