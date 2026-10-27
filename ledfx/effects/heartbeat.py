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
    Trigger,
    color_array,
    frame_step,
)

# The "dub" follows the "lub" this long after the beat, a little weaker
SECOND_BEAT_DELAY = 0.18
SECOND_BEAT_STRENGTH = 0.6
# Pulses alive at once: a lub and a dub per beat, with room for overlap
MAX_PULSES = 8


class Heartbeat(AudioReactiveEffect):
    NAME = "Heartbeat"
    CATEGORY = CUSTOM_CATEGORY

    class Config(AudioReactiveEffect.Config):
        color: Color = Field("#FF0022", description="Color of the heartbeat")
        pulse_size: CoercedFloat = Field(
            0.6,
            description="How far a pulse spreads from the center, as a share of the strip",
            ge=0.1,
            le=1.0,
        )
        decay: CoercedFloat = Field(
            6.0,
            description="How fast a pulse fades. Higher -> shorter pulses",
            ge=1.0,
            le=20.0,
        )
        double_beat: bool = Field(
            True, description="Follow each beat with a second, weaker pulse (lub-dub)"
        )
        resting_glow: CoercedFloat = Field(
            0.08,
            description="Brightness between the beats",
            ge=0.0,
            le=0.5,
        )
        trigger: Trigger = Field(
            "Beat", description="Beat on the bass or on every percussive hit"
        )

    config = TypedConfig(Config)

    def on_activate(self, pixel_count: int) -> None:
        center = (pixel_count - 1) / 2
        self._distance: FloatArray = np.abs(np.arange(pixel_count) - center)
        self._ages: FloatArray = np.full(MAX_PULSES, np.inf)
        self._strengths: FloatArray = np.zeros(MAX_PULSES)
        self._dub_at: float | None = None
        self._latch = BeatLatch()

    @override
    def config_updated(self, config: object) -> None:
        self._color = color_array(self.config.color)

    @override
    def audio_data_updated(self, data: AudioAnalysisSource) -> None:
        self._latch.listen(data, self.config.trigger)

    def _pulse(self, strength: float) -> None:
        # Reuse the oldest slot: a pulse that old has long faded
        slot = int(np.argmax(self._ages))
        self._ages[slot] = 0.0
        self._strengths[slot] = strength

    @override
    def render(self) -> None:
        dt = frame_step(self.passed)
        self._ages += dt
        if self._latch.take(self.now):
            self._pulse(1.0)
            if self.config.double_beat:
                self._dub_at = self.now + SECOND_BEAT_DELAY
        if self._dub_at is not None and self.now >= self._dub_at:
            self._pulse(SECOND_BEAT_STRENGTH)
            self._dub_at = None

        level = np.full(self.pixel_count, self.config.resting_glow)
        reach = max(1.0, self.config.pulse_size * self.pixel_count / 2)
        for age, strength in zip(self._ages, self._strengths, strict=True):
            amount = strength * np.exp(-age * self.config.decay)
            if amount < 0.005:
                continue
            # The pulse swells outward quickly, then holds while it fades
            radius = reach * (0.3 + 0.7 * (1 - np.exp(-age * 8)))
            np.maximum(
                level, amount * np.exp(-((self._distance / radius) ** 2)), out=level
            )
        self.pixels = self._color * level[:, None]
