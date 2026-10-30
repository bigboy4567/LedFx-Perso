from typing import Literal

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

# Higher harmonics die out faster, as on a real string
HARMONIC_DAMPING = 0.6
# A still string glows this faintly
STILL = 0.04

Pluck = Literal["Random", "Center", "Near the end"]


class VibratingString(AudioReactiveEffect):
    NAME = "Vibrating String"
    CATEGORY = CUSTOM_CATEGORY

    class Config(AudioReactiveEffect.Config):
        color_up: Color = Field(
            "#FF6A00", description="Color of the string swinging one way"
        )
        color_down: Color = Field(
            "#00B4FF", description="Color of the string swinging the other way"
        )
        harmonics: CoercedInt = Field(
            6, description="Harmonics the string vibrates in", ge=1, le=12
        )
        slow_motion: CoercedFloat = Field(
            1.5, description="Swings per second of the lowest harmonic", ge=0.2, le=8.0
        )
        sustain: CoercedFloat = Field(
            2.0, description="Seconds the string keeps ringing", ge=0.3, le=10.0
        )
        pluck: Pluck = Field("Random", description="Where the string is plucked")
        trigger: Trigger = Field(
            "Beat", description="Pluck on the bass or on every percussive hit"
        )

    config = TypedConfig(Config)

    def on_activate(self, pixel_count: int) -> None:
        # Both ends are fixed, just past the first and last pixels
        self._u: FloatArray = (np.arange(pixel_count) + 1) / (pixel_count + 1)
        self._amplitudes: FloatArray = np.zeros(12)
        self._phases: FloatArray = np.zeros(12)
        self._highs = 0.0
        self._latch = BeatLatch()

    @override
    def config_updated(self, config: object) -> None:
        if not hasattr(self, "_rng"):
            self._rng = np.random.default_rng()
        self._up = color_array(self.config.color_up)
        self._down = color_array(self.config.color_down)

    @override
    def audio_data_updated(self, data: AudioAnalysisSource) -> None:
        self._highs = float(data.high_power())
        self._latch.listen(data, self.config.trigger)

    def _pluck(self) -> None:
        match self.config.pluck:
            case "Random":
                point = float(self._rng.uniform(0.15, 0.85))
            case "Center":
                point = 0.5
            case "Near the end":
                point = 0.12
        harmonic = np.arange(1, 13)
        # A string pulled aside at one point and let go rings in these proportions;
        # bright music lets more of the high harmonics through
        brightness = 1.5 + 1.5 * (1 - self._highs)
        weights = np.sin(np.pi * harmonic * point) / harmonic**brightness
        weights[self.config.harmonics :] = 0
        peak = np.abs(weights).sum()
        if peak > 0:
            self._amplitudes = weights / peak
            self._phases[:] = 0.0

    @override
    def render(self) -> None:
        dt = frame_step(self.passed)
        if self._latch.take(self.now):
            self._pluck()
        harmonic = np.arange(1, 13)
        self._phases += 2 * np.pi * harmonic * self.config.slow_motion * dt
        decay = 3 / self.config.sustain * (1 + HARMONIC_DAMPING * (harmonic - 1))
        self._amplitudes *= np.exp(-dt * decay)

        active = np.flatnonzero(np.abs(self._amplitudes) > 1e-4)
        swing = np.zeros_like(self._u)
        for k in active:
            swing += (
                self._amplitudes[k]
                * np.cos(self._phases[k])
                * np.sin(np.pi * (k + 1) * self._u)
            )
        level = np.clip(np.abs(swing) * 1.6, 0, 1)
        colors = np.where((swing >= 0)[:, None], self._up, self._down)
        self.pixels = colors * np.maximum(level, STILL)[:, None]
