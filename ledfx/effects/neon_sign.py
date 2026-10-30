from typing import ClassVar

import numpy as np
from pydantic import Field
from typing_extensions import override

from ledfx.configuration.fields import CoercedFloat, CoercedInt
from ledfx.configuration.plugin import TypedConfig
from ledfx.effects.audio import AudioAnalysisSource, AudioReactiveEffect
from ledfx.effects.gradient import GradientEffect
from ledfx.effects.utils.custom import (
    CUSTOM_CATEGORY,
    BeatLatch,
    FloatArray,
    IntArray,
    Trigger,
    frame_step,
    segment_widths,
)

# A tube switched back on stutters through these on and off steps, in seconds
STRIKE = ((0.0, 0.0), (0.05, 1.0), (0.09, 0.0), (0.16, 0.8), (0.2, 0.1), (0.3, 1.0))
STRIKE_TIME = STRIKE[-1][0]
# Brightness of a tube that dips for a frame on a bad contact
DIP_LEVEL = 0.35
# Neon glows softly past the ends of the glass
EDGE_FALLOFF = 0.15


class NeonSign(AudioReactiveEffect, GradientEffect):
    NAME = "Neon Sign"
    CATEGORY = CUSTOM_CATEGORY
    # Effect declares HIDDEN_KEYS = None, so every list override trips bad-override.
    HIDDEN_KEYS: ClassVar[list[str]] = ["gradient_roll"]  # pyrefly: ignore[bad-override]

    class Config(GradientEffect.Config):
        tubes: CoercedInt = Field(
            5, description="Glass tubes along the strip", ge=1, le=16
        )
        faulty: CoercedFloat = Field(
            0.5,
            description="How often the treble makes a tube flicker on a bad contact",
            ge=0.0,
            le=1.0,
        )
        trigger: Trigger = Field(
            "Beat",
            description="Switch a tube off and back on with the bass or every percussive hit",
        )

    config = TypedConfig(Config)

    def on_activate(self, pixel_count: int) -> None:
        self._layout(pixel_count)
        self._highs = 0.0
        self._latch = BeatLatch()

    def _layout(self, pixel_count: int) -> None:
        widths = segment_widths(pixel_count, self.config.tubes)
        count = widths.size
        self._tube: IntArray = np.repeat(np.arange(count), widths)
        starts = np.cumsum(widths) - widths
        within = (np.arange(pixel_count) - starts[self._tube] + 0.5) / widths[
            self._tube
        ]
        # The glass ends a little short of its space, and glows dimmer at its ends
        edge = np.minimum(within, 1 - within)
        self._shape: FloatArray = np.clip(edge / EDGE_FALLOFF, 0, 1) ** 0.5
        self._shape[widths[self._tube] < 4] = 1.0
        self._hues: FloatArray = (np.arange(count) + 0.5) / count
        self._struck: FloatArray = np.full(count, np.inf)

    @override
    def config_updated(self, config: object) -> None:
        if not hasattr(self, "_rng"):
            self._rng = np.random.default_rng()
        pixels = getattr(self, "pixels", None)
        if pixels is not None and hasattr(self, "_struck"):
            self._layout(len(pixels))

    @override
    def audio_data_updated(self, data: AudioAnalysisSource) -> None:
        self._highs = float(data.high_power())
        self._latch.listen(data, self.config.trigger)

    @override
    def render(self) -> None:
        dt = frame_step(self.passed)
        count = self._struck.size
        self._struck += dt
        if self._latch.take(self.now):
            self._struck[self._rng.integers(count)] = 0.0

        levels = np.ones(count)
        for start, level in STRIKE:
            levels[self._struck >= start] = level
        levels[self._struck >= STRIKE_TIME] = 1.0
        dipping = self._rng.random(count) < self.config.faulty * self._highs * dt * 6
        levels[dipping] = np.minimum(levels[dipping], DIP_LEVEL)
        # A barely visible mains hum keeps the glass alive
        levels *= 0.94 + 0.06 * self._rng.random(count)

        colors = self.get_gradient_color_vectorized1d(self._hues)
        level = levels[self._tube] * self._shape
        self.pixels = colors[self._tube] * level[:, None]
