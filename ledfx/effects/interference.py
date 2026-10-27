import numpy as np
from pydantic import Field
from typing_extensions import override

from ledfx.configuration.fields import CoercedFloat, Color
from ledfx.configuration.plugin import TypedConfig
from ledfx.effects.audio import AudioAnalysisSource, AudioReactiveEffect
from ledfx.effects.utils.custom import (
    CUSTOM_CATEGORY,
    FloatArray,
    color_array,
    frame_step,
)

# Brightness of a wave whose band is silent
QUIET = 0.3


class Interference(AudioReactiveEffect):
    NAME = "Interference"
    CATEGORY = CUSTOM_CATEGORY

    class Config(AudioReactiveEffect.Config):
        bass_color: Color = Field(
            "#FF0080", description="Color of the wave driven by the bass"
        )
        treble_color: Color = Field(
            "#00FFD0", description="Color of the wave driven by the treble"
        )
        wavelength: CoercedFloat = Field(
            0.25,
            description="Length of one wave, as a share of the strip",
            ge=0.05,
            le=1.0,
        )
        speed: CoercedFloat = Field(
            0.5, description="How fast the waves travel", ge=0.0, le=3.0
        )

    config = TypedConfig(Config)

    def on_activate(self, pixel_count: int) -> None:
        self._x: FloatArray = np.arange(pixel_count, dtype=float)
        self._phases: FloatArray = np.zeros(2)
        self._lows = 0.0
        self._highs = 0.0

    @override
    def config_updated(self, config: object) -> None:
        self._bass = color_array(self.config.bass_color)
        self._treble = color_array(self.config.treble_color)

    @override
    def audio_data_updated(self, data: AudioAnalysisSource) -> None:
        self._lows = float(data.lows_power())
        self._highs = float(data.high_power())

    @override
    def render(self) -> None:
        dt = frame_step(self.passed)
        # Each wave runs faster when its own band is loud
        self._phases += (
            dt * self.config.speed * (1 + np.array((self._lows, self._highs)))
        )
        cycles = self._x / max(1.0, self.config.wavelength * len(self._x))
        # The two waves travel in opposite directions and pass through each other
        bass = (0.5 + 0.5 * np.sin(2 * np.pi * (cycles - self._phases[0]))) ** 2
        treble = (0.5 + 0.5 * np.sin(2 * np.pi * (cycles + self._phases[1]))) ** 2
        bass *= QUIET + (1 - QUIET) * self._lows
        treble *= QUIET + (1 - QUIET) * self._highs
        pixels = self._bass * bass[:, None] + self._treble * treble[:, None]
        self.pixels = np.minimum(pixels, 255)
