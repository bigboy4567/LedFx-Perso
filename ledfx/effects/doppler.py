import numpy as np
from pydantic import Field
from typing_extensions import override

from ledfx.configuration.fields import CoercedFloat, CoercedInt, Color
from ledfx.configuration.plugin import TypedConfig
from ledfx.effects.audio import AudioAnalysisSource, AudioReactiveEffect
from ledfx.effects.utils.custom import (
    CUSTOM_CATEGORY,
    FloatArray,
    TempoTracker,
    color_array,
    frame_step,
    splat,
)

# The waves spread at this speed, in strips per second; the source moves at a share of it
WAVE_SPEED = 1.0
# Waves alive at once, at most; the oldest makes room
MAX_WAVES = 64
# A wave fades as it spreads, gone by this distance
WAVE_REACH = 0.6
# Ahead of the source the waves crowd together and turn blue, behind it they stretch and redden
AHEAD = color_array("#2060FF")
BEHIND = color_array("#FF2010")


class Doppler(AudioReactiveEffect):
    NAME = "Doppler"
    CATEGORY = CUSTOM_CATEGORY

    class Config(AudioReactiveEffect.Config):
        color: Color = Field("#40FF70", description="Color of the source")
        speed: CoercedFloat = Field(
            0.6,
            description="How fast the source moves, as a share of the speed of its waves",
            ge=0.1,
            le=0.95,
        )
        waves_per_beat: CoercedInt = Field(
            4, description="Waves sent out on each beat of the song", ge=1, le=8
        )

    config = TypedConfig(Config)

    def on_activate(self, pixel_count: int) -> None:
        self._x: FloatArray = np.arange(pixel_count, dtype=float)
        # The source's position in strip lengths, and which way it goes
        self.source = 0.5
        self.heading = 1.0
        # Each wave: where it was sent from, when, and which way the source was going
        self._waves: FloatArray = np.zeros((0, 3))
        self._next = 0.0
        self._tempo = TempoTracker()

    @override
    def config_updated(self, config: object) -> None:
        self._color = color_array(self.config.color)

    @override
    def audio_data_updated(self, data: AudioAnalysisSource) -> None:
        self._tempo.listen(data)

    def _emit(self) -> None:
        wave = np.array([[self.source, self.now, self.heading]])
        self._waves = np.concatenate((self._waves, wave))[-MAX_WAVES:]

    @override
    def render(self) -> None:
        dt = frame_step(self.passed)
        self.source += self.heading * self.config.speed * WAVE_SPEED * dt
        # The source turns back at the ends of the strip
        if not 0 <= self.source <= 1:
            self.heading = -self.heading
            self.source = float(np.clip(self.source, 0, 1))
        if self.now >= self._next:
            self._emit()
            self._next = (
                self.now + self._tempo.beat_length() / self.config.waves_per_beat
            )
        alive = (self.now - self._waves[:, 1]) * WAVE_SPEED < WAVE_REACH
        self._waves = self._waves[alive]

        n = self.pixel_count
        span = max(n - 1, 1)
        width = max(0.6, n / 200)
        ahead, behind = np.zeros(n), np.zeros(n)
        for origin, sent, heading in self._waves:
            radius = (self.now - sent) * WAVE_SPEED
            fade = 1 - radius / WAVE_REACH
            for side in (1.0, -1.0):
                rings = ahead if side == heading else behind
                splat(rings, self._x, (origin + side * radius) * span, width, fade)
        pixels = AHEAD * ahead[:, None] + BEHIND * behind[:, None]
        source = np.zeros(n)
        splat(source, self._x, self.source * span, max(1.0, n / 60), 1.0)
        self.pixels = np.clip(np.maximum(pixels, self._color * source[:, None]), 0, 255)
