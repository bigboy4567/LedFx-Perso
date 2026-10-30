from typing import ClassVar, Literal

import numpy as np
from pydantic import Field
from typing_extensions import override

from ledfx.configuration.fields import CoercedFloat, CoercedInt
from ledfx.configuration.plugin import TypedConfig
from ledfx.effects.audio import AudioAnalysisSource, AudioReactiveEffect
from ledfx.effects.gradient import GradientEffect
from ledfx.effects.utils.custom import (
    CUSTOM_CATEGORY,
    FloatArray,
    TempoTracker,
    volume_of,
)

# Beats for one sweep up and back down
SWEEPS = {"1 beat": 1, "1 bar": 4, "2 bars": 8, "4 bars": 16}
# The notches crowd together as the sweep rises, from this share of their count to the next
SPREAD = (0.6, 1.4)
RING = np.array((255.0, 255.0, 255.0))

Sweep = Literal["1 beat", "1 bar", "2 bars", "4 bars"]


class Phaser(AudioReactiveEffect, GradientEffect):
    NAME = "Phaser"
    CATEGORY = CUSTOM_CATEGORY
    # Effect declares HIDDEN_KEYS = None, so every list override trips bad-override.
    HIDDEN_KEYS: ClassVar[list[str]] = ["gradient_roll"]  # pyrefly: ignore[bad-override]

    class Config(GradientEffect.Config):
        notches: CoercedInt = Field(
            4, description="Dark notches sweeping through the light", ge=1, le=12
        )
        sweep: Sweep = Field(
            "1 bar", description="Time for one sweep, in step with the song"
        )
        depth: CoercedFloat = Field(
            0.85, description="How dark the notches go", ge=0.0, le=1.0
        )
        resonance: CoercedFloat = Field(
            0.5,
            description="How sharp the notches are, and how brightly their edges ring",
            ge=0.0,
            le=1.0,
        )

    config = TypedConfig(Config)

    def on_activate(self, pixel_count: int) -> None:
        self._u: FloatArray = np.arange(pixel_count) / max(pixel_count - 1, 1)
        self._volume = 0.0
        self._tempo = TempoTracker()

    @override
    def audio_data_updated(self, data: AudioAnalysisSource) -> None:
        self._tempo.listen(data)
        self._volume = volume_of(data)

    @override
    def render(self) -> None:
        sweep = 0.5 - 0.5 * float(
            np.cos(2 * np.pi * self._tempo.beats / SWEEPS[self.config.sweep])
        )
        low, high = SPREAD
        count = self.config.notches * (low + (high - low) * sweep)
        sharp = 1 + 6 * self.config.resonance
        notch = (
            0.5 + 0.5 * np.cos(2 * np.pi * (self._u * count + sweep * 0.5))
        ) ** sharp
        level = 1 - self.config.depth * notch
        colors = self.get_gradient_color_vectorized1d(self._u)
        pixels = colors * level[:, None]
        # The edges of the notches ring with the music
        ring = 4 * notch * (1 - notch) * self.config.resonance * self._volume * 0.4
        self.pixels = np.clip(pixels + (RING - pixels) * ring[:, None], 0, 255)
