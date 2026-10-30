from typing import ClassVar, Literal

import numpy as np
from pydantic import Field
from typing_extensions import override

from ledfx.configuration.fields import CoercedFloat, CoercedInt
from ledfx.configuration.plugin import TypedConfig
from ledfx.effects.audio import AudioAnalysisSource, AudioReactiveEffect
from ledfx.effects.gradient import GradientEffect
from ledfx.effects.utils.corsair import CORSAIR_CATEGORY, FAN_HUB, fan_layout
from ledfx.effects.utils.custom import (
    FloatArray,
    TempoTracker,
    frame_step,
)

# How long a blade's glowing tail is, as a share of the gap between two blades
TAIL = 3.0

Spin = Literal["Same way", "Alternate"]


class FanRotor(AudioReactiveEffect, GradientEffect):
    NAME = "Fan Rotor"
    CATEGORY = CORSAIR_CATEGORY
    # Effect declares HIDDEN_KEYS = None, so every list override trips bad-override.
    HIDDEN_KEYS: ClassVar[list[str]] = ["gradient_roll"]  # pyrefly: ignore[bad-override]

    class Config(GradientEffect.Config):
        blades: CoercedInt = Field(
            2, description="Glowing blades on each fan", ge=1, le=4
        )
        turns_per_beat: CoercedFloat = Field(
            0.5, description="Turns of the blades per beat of the song", ge=0.1, le=4.0
        )
        spin: Spin = Field(
            "Alternate",
            description="All fans spin the same way, or every other one the other way",
        )
        hub_pulse: bool = Field(True, description="The hubs glow with the bass")

    config = TypedConfig(Config)

    def on_activate(self, pixel_count: int) -> None:
        self._fans = fan_layout(pixel_count)
        self._turn = 0.0
        self._beats = 0.0
        self._lows = 0.0
        self._volume = 0.0
        self._tempo = TempoTracker()

    @override
    def audio_data_updated(self, data: AudioAnalysisSource) -> None:
        self._tempo.listen(data)
        self._lows += (float(data.lows_power()) - self._lows) * 0.3

    @override
    def render(self) -> None:
        dt = frame_step(self.passed)
        moved = self._tempo.beats - self._beats
        self._beats = self._tempo.beats
        # The blades keep time with the song, and idle round slowly with no tempo
        self._turn += moved * self.config.turns_per_beat + dt * 0.05

        fans = self._fans
        heading = np.where(
            (self.config.spin == "Alternate") & (fans.fan % 2 == 1), -1.0, 1.0
        )
        blades = self.config.blades
        # How far behind the nearest blade each LED is, as a share of the gap between blades
        behind = ((self._turn - fans.angle * heading) * blades) % 1
        level: FloatArray = np.exp(-behind * TAIL)
        colors = self.get_gradient_color_vectorized1d(
            (fans.fan + 0.5) / max(fans.count, 1) * 0.999
        )
        hub = fans.ring == FAN_HUB
        if self.config.hub_pulse:
            level = np.where(hub, 0.15 + 0.85 * min(1.0, self._lows * 1.5), level)
        self.pixels = colors * level[:, None]
