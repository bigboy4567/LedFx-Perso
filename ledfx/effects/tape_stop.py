from typing import Literal

import numpy as np
from pydantic import Field
from typing_extensions import override

from ledfx.configuration.fields import CoercedFloat, CoercedInt
from ledfx.configuration.plugin import TypedConfig
from ledfx.effects.audio import AudioAnalysisSource, AudioReactiveEffect
from ledfx.effects.utils.custom import (
    AUDIO_STEP,
    CUSTOM_CATEGORY,
    FloatArray,
    TempoTracker,
    frame_step,
    hue_colors,
    volume_of,
)

# A break: the volume falls below this share of its recent peak; it is over above the second
BREAK_BELOW = 0.3
BREAK_OVER = 0.6
# The recent peak fades this fast, per second, so a long quiet song still has breaks
PEAK_FADE = 0.2
# Hue step from one color band to the next
BAND_HUE = 0.13
SLOWED = np.array((90.0, 0.0, 10.0))

Stop = Literal["On breaks", "Every 4 bars"]


class TapeStop(AudioReactiveEffect):
    NAME = "Tape Stop"
    CATEGORY = CUSTOM_CATEGORY

    class Config(AudioReactiveEffect.Config):
        stop: Stop = Field(
            "On breaks",
            description="Wind the tape down when the music breaks, or on the last beat of every 4 bars",
        )
        stop_time: CoercedFloat = Field(
            0.8, description="Seconds the tape takes to wind down", ge=0.2, le=3.0
        )
        band_width: CoercedInt = Field(
            12, description="Pixels per color band on the tape", ge=2, le=200
        )

    config = TypedConfig(Config)

    def on_activate(self, pixel_count: int) -> None:
        self._x: FloatArray = np.arange(pixel_count, dtype=float)
        # How far the tape has run, in bands, and its speed as a share of full speed
        self._offset = 0.0
        self._speed = 1.0
        self._stopping = False
        self._volume = 0.0
        self._peak = 0.0
        self._tempo = TempoTracker()

    @override
    def audio_data_updated(self, data: AudioAnalysisSource) -> None:
        self._tempo.listen(data)
        self._volume += (volume_of(data) - self._volume) * 0.2
        self._peak = max(
            self._volume, self._peak * float(np.exp(-AUDIO_STEP * PEAK_FADE))
        )

    def _watch(self) -> None:
        if self.config.stop == "Every 4 bars":
            self._stopping = self._tempo.beats % 16 >= 15
        elif self._stopping:
            self._stopping = self._volume < BREAK_OVER * self._peak
        else:
            self._stopping = (
                self._peak > 0.02 and self._volume < BREAK_BELOW * self._peak
            )

    @override
    def render(self) -> None:
        dt = frame_step(self.passed)
        self._watch()
        # The tape winds down slowly and comes back up to speed twice as fast
        if self._stopping:
            self._speed = max(0.0, self._speed - dt / self.config.stop_time)
        else:
            self._speed = min(1.0, self._speed + 2 * dt / self.config.stop_time)
        # One band runs by per beat at full speed
        self._offset += dt / self._tempo.beat_length() * self._speed

        band = np.floor(self._x / self.config.band_width + self._offset)
        colors = hue_colors(band * BAND_HUE)
        # Slowing down, the light drops and reddens like the pitch of the music
        speed = self._speed
        self.pixels = colors * (0.2 + 0.8 * speed) + SLOWED * (1 - speed) * 0.5
