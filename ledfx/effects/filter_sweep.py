from typing import ClassVar, Literal

import numpy as np
from pydantic import Field
from typing_extensions import override

from ledfx.configuration.fields import CoercedFloat
from ledfx.configuration.plugin import TypedConfig
from ledfx.effects.audio import AudioAnalysisSource, AudioReactiveEffect
from ledfx.effects.gradient import GradientEffect
from ledfx.effects.utils.custom import (
    CUSTOM_CATEGORY,
    FloatArray,
    PeakTracker,
    frame_step,
    volume_of,
)

# Width of the soft cut, and of the resonant peak at the cutoff, as a share of the strip
SLOPE = 0.03
PEAK = 0.025
WHITE = np.array((255.0, 255.0, 255.0))

Mode = Literal["Low-pass", "High-pass"]


class FilterSweep(AudioReactiveEffect, GradientEffect):
    NAME = "Filter Sweep"
    CATEGORY = CUSTOM_CATEGORY
    # Effect declares HIDDEN_KEYS = None, so every list override trips bad-override.
    HIDDEN_KEYS: ClassVar[list[str]] = ["gradient_roll"]  # pyrefly: ignore[bad-override]

    class Config(GradientEffect.Config):
        mode: Mode = Field(
            "Low-pass",
            description="Low-pass lights the strip up to the cutoff, high-pass from it to the end",
        )
        resonance: CoercedFloat = Field(
            0.6, description="How brightly the cutoff rings", ge=0.0, le=1.0
        )
        response: CoercedFloat = Field(
            4.0, description="How quickly the cutoff follows the music", ge=1.0, le=20.0
        )

    config = TypedConfig(Config)

    def on_activate(self, pixel_count: int) -> None:
        self._u: FloatArray = np.arange(pixel_count) / max(pixel_count - 1, 1)
        self.cutoff = 0.5
        self._brightness = 0.5
        self._volume = 0.0
        self._peaks = PeakTracker(3)

    @override
    def audio_data_updated(self, data: AudioAnalysisSource) -> None:
        bands = np.array(
            (data.lows_power(), data.mids_power(), data.high_power()), dtype=float
        )
        level = self._peaks.update(bands)
        total = float(level.sum())
        # Bright, trebly music opens the filter; heavy bass closes it down
        self._brightness = (
            float(level[1] * 0.5 + level[2]) / total if total > 0 else 0.0
        )
        self._volume = volume_of(data)

    @override
    def render(self) -> None:
        dt = frame_step(self.passed)
        target = 0.1 + 0.9 * min(1.0, self._brightness * 1.3)
        self.cutoff += (target - self.cutoff) * min(1.0, dt * self.config.response)

        u = self._u
        edge = self.cutoff if self.config.mode == "Low-pass" else 1 - self.cutoff
        ahead = edge - u if self.config.mode == "Low-pass" else u - edge
        passed = np.clip(ahead / SLOPE + 0.5, 0, 1)
        colors = self.get_gradient_color_vectorized1d(u)
        pixels = colors * (passed * (0.35 + 0.65 * min(1.0, self._volume * 2)))[:, None]
        ring = np.exp(-(((u - edge) / PEAK) ** 2)) * self.config.resonance
        self.pixels = np.clip(pixels + (WHITE - pixels) * ring[:, None] * 0.8, 0, 255)
