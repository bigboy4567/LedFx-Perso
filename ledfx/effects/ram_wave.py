from typing import ClassVar

import numpy as np
from pydantic import Field
from typing_extensions import override

from ledfx.configuration.fields import CoercedFloat
from ledfx.configuration.plugin import TypedConfig
from ledfx.effects.audio import AudioAnalysisSource, AudioReactiveEffect
from ledfx.effects.gradient import GradientEffect
from ledfx.effects.utils.corsair import CORSAIR_CATEGORY, ram_layout
from ledfx.effects.utils.custom import (
    BeatLatch,
    FloatArray,
    TempoTracker,
    frame_step,
    volume_of,
)

# Half the height of the glowing band, as a share of a stick
BAND = 0.18
WHITE = np.array((255.0, 255.0, 255.0))


class RamWave(AudioReactiveEffect, GradientEffect):
    NAME = "RAM Wave"
    CATEGORY = CORSAIR_CATEGORY
    # Effect declares HIDDEN_KEYS = None, so every list override trips bad-override.
    HIDDEN_KEYS: ClassVar[list[str]] = ["gradient_roll"]  # pyrefly: ignore[bad-override]

    class Config(GradientEffect.Config):
        waves_per_beat: CoercedFloat = Field(
            0.5,
            description="Waves passing across the sticks per beat of the song",
            ge=0.1,
            le=2.0,
        )
        spread: CoercedFloat = Field(
            0.25,
            description="How far apart in the wave neighbouring sticks are, as a share of a wave",
            ge=0.0,
            le=0.5,
        )

    config = TypedConfig(Config)

    def on_activate(self, pixel_count: int) -> None:
        self._ram = ram_layout(pixel_count)
        self._phase = 0.0
        self._beats = 0.0
        self._volume = 0.0
        self._flash = 0.0
        self._tempo = TempoTracker()
        self._latch = BeatLatch()

    @override
    def audio_data_updated(self, data: AudioAnalysisSource) -> None:
        self._tempo.listen(data)
        self._volume += (volume_of(data) - self._volume) * 0.2
        self._latch.listen(data, "Beat")

    def heights(self) -> FloatArray:
        """Where the glowing band sits on each stick, 0 at the bottom, 1 at the top."""
        sticks = np.arange(self._ram.sticks)
        swing = 0.1 + 0.35 * min(1.0, self._volume * 2)
        return 0.5 + swing * np.sin(
            2 * np.pi * (self._phase - sticks * self.config.spread)
        )

    @override
    def render(self) -> None:
        dt = frame_step(self.passed)
        moved = self._tempo.beats - self._beats
        self._beats = self._tempo.beats
        self._phase += moved * self.config.waves_per_beat + dt * 0.05
        self._flash *= float(np.exp(-dt * 6))
        if self._latch.take(self.now):
            self._flash = 1.0

        ram = self._ram
        offset = (ram.height - self.heights()[ram.stick]) / BAND
        level = np.exp(-(offset**2))
        colors = self.get_gradient_color_vectorized1d(
            (ram.stick + 0.5) / max(ram.sticks, 1) * 0.999
        )
        pixels = colors * level[:, None]
        # On the beat the band's core flashes white
        self.pixels = np.clip(
            pixels + (WHITE - pixels) * (level**4 * self._flash * 0.7)[:, None], 0, 255
        )
