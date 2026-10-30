import numpy as np
from pydantic import Field
from typing_extensions import override

from ledfx.configuration.fields import CoercedFloat, CoercedInt, Color
from ledfx.configuration.plugin import TypedConfig
from ledfx.effects.audio import AudioAnalysisSource, AudioReactiveEffect
from ledfx.effects.utils.custom import (
    CUSTOM_CATEGORY,
    BeatLatch,
    FloatArray,
    Trigger,
    color_array,
    frame_step,
)

# A strike is a few return strokes in quick succession, the first the brightest
STROKE_GAPS = (0.0, 0.06, 0.13, 0.22)
STROKE_STRENGTHS = (1.0, 0.55, 0.8, 0.4)
# How fast a single stroke dies out
STROKE_DECAY = 25.0
# Share of the strip a bolt can cover
BOLT_SHARES = (0.15, 0.6)
# The whole sky lights up faintly with each stroke
SKY_GLOW = 0.12


class Lightning(AudioReactiveEffect):
    NAME = "Lightning"
    CATEGORY = CUSTOM_CATEGORY

    class Config(AudioReactiveEffect.Config):
        color: Color = Field("#9EB4FF", description="Color of the bolts")
        branches: CoercedInt = Field(
            3, description="Side branches forking off each bolt", ge=0, le=8
        )
        sky_glow: bool = Field(
            True, description="Light the whole strip faintly with each strike"
        )
        rumble: CoercedFloat = Field(
            0.5,
            description="How much the bass keeps the sky flickering between strikes",
            ge=0.0,
            le=1.0,
        )
        trigger: Trigger = Field(
            "Beat", description="Strike on the bass or on every percussive hit"
        )

    config = TypedConfig(Config)

    def on_activate(self, pixel_count: int) -> None:
        self._bolt: FloatArray = np.zeros(pixel_count)
        self._age = np.inf
        self._lows = 0.0
        self._latch = BeatLatch()

    @override
    def config_updated(self, config: object) -> None:
        if not hasattr(self, "_rng"):
            self._rng = np.random.default_rng()
        self._color = color_array(self.config.color)

    @override
    def audio_data_updated(self, data: AudioAnalysisSource) -> None:
        self._lows = float(data.lows_power())
        self._latch.listen(data, self.config.trigger)

    def _segment(self, start: float, length: float, strength: float) -> None:
        n = self._bolt.size
        lo = int(np.clip(start, 0, n - 1))
        hi = int(np.clip(start + length, lo + 1, n))
        # A jagged channel: bright and dim stretches along its length
        jagged = strength * self._rng.uniform(0.45, 1.0, hi - lo)
        np.maximum(self._bolt[lo:hi], jagged, out=self._bolt[lo:hi])

    def _strike(self) -> None:
        n = self._bolt.size
        self._bolt[:] = 0
        length = max(1.0, n * self._rng.uniform(*BOLT_SHARES))
        start = self._rng.uniform(0, max(n - length, 0))
        self._segment(start, length, 1.0)
        for _ in range(self.config.branches):
            # Forks leave from a point on the bolt and fade as they go
            fork = start + self._rng.uniform(0, length)
            reach = length * self._rng.uniform(0.1, 0.35)
            side = fork if self._rng.random() < 0.5 else fork - reach
            self._segment(side, reach, self._rng.uniform(0.25, 0.55))
        self._age = 0.0

    @override
    def render(self) -> None:
        self._age += frame_step(self.passed)
        if self._latch.take(self.now):
            self._strike()

        flash = 0.0
        for gap, strength in zip(STROKE_GAPS, STROKE_STRENGTHS, strict=True):
            since = self._age - gap
            if since >= 0:
                flash = max(flash, strength * float(np.exp(-since * STROKE_DECAY)))
        level = self._bolt * flash
        if self.config.sky_glow:
            # Distant thunder: the bass keeps a dim, restless glow in the clouds
            restless = self.config.rumble * self._lows * self._rng.uniform(0.0, 0.1)
            level = np.maximum(level, SKY_GLOW * flash + restless)
        # The brightest part of a bolt burns white
        pixels = self._color * level[:, None]
        pixels += (255 - pixels) * (level**3)[:, None]
        self.pixels = np.clip(pixels, 0, 255)
