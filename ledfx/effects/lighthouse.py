from typing import Literal

import numpy as np
from pydantic import Field
from typing_extensions import override

from ledfx.configuration.fields import CoercedFloat, Color
from ledfx.configuration.plugin import TypedConfig
from ledfx.effects.audio import AudioAnalysisSource, AudioReactiveEffect
from ledfx.effects.utils.custom import (
    CUSTOM_CATEGORY,
    FloatArray,
    TempoTracker,
    color_array,
    frame_step,
)

# Beats per turn of the lamp when following the song; seconds per turn when steady
BEATS_PER_TURN = {"Per bar": 4, "Per 2 bars": 8}
STEADY_TURN = 6.0
# The beam is a narrow cone: the higher the power, the narrower
BEAM_POWER = 3
# How sharply the lamp blazes as it faces the viewer
BLAZE_POWER = 30
FOG = 0.03

Rotation = Literal["Per bar", "Per 2 bars", "Steady"]


class Lighthouse(AudioReactiveEffect):
    NAME = "Lighthouse"
    CATEGORY = CUSTOM_CATEGORY

    class Config(AudioReactiveEffect.Config):
        color: Color = Field("#FFF0C0", description="Color of the lamp")
        rotation: Rotation = Field(
            "Per bar",
            description="One turn of the lamp per bar, per two bars, or steadily",
        )
        reach: CoercedFloat = Field(
            0.35,
            description="How far the beam shows in the fog, as a share of the strip",
            ge=0.05,
            le=1.0,
        )
        lamp_position: CoercedFloat = Field(
            0.5,
            description="Where the lighthouse stands along the strip",
            ge=0.0,
            le=1.0,
        )

    config = TypedConfig(Config)

    def on_activate(self, pixel_count: int) -> None:
        self._u: FloatArray = np.arange(pixel_count) / max(pixel_count - 1, 1)
        self._turns = 0.0
        self._beats = 0.0
        self._tempo = TempoTracker()

    @override
    def config_updated(self, config: object) -> None:
        self._color = color_array(self.config.color)

    @override
    def audio_data_updated(self, data: AudioAnalysisSource) -> None:
        self._tempo.listen(data)

    @override
    def render(self) -> None:
        dt = frame_step(self.passed)
        moved = self._tempo.beats - self._beats
        self._beats = self._tempo.beats
        rotation = self.config.rotation
        self._turns += (
            dt / STEADY_TURN
            if rotation == "Steady"
            else moved / BEATS_PER_TURN[rotation]
        )

        angle = 2 * np.pi * self._turns
        # The beam points along the strip one way, then the other, facing the viewer between
        sideways, facing = float(np.cos(angle)), float(np.sin(angle))
        from_lamp = (self._u - self.config.lamp_position) * np.sign(sideways)
        beam = np.where(from_lamp > 0, np.exp(-from_lamp / self.config.reach), 0.0)
        beam *= abs(sideways) ** BEAM_POWER
        blaze = max(0.0, facing) ** BLAZE_POWER
        lamp = np.exp(-(((self._u - self.config.lamp_position) / 0.02) ** 2))
        level = FOG + 0.8 * beam + 0.9 * blaze + lamp * (0.4 + 0.6 * max(0.0, facing))
        self.pixels = self._color * np.clip(level, 0, 1)[:, None]
