import numpy as np
from pydantic import Field
from typing_extensions import override

from ledfx.configuration.fields import CoercedFloat, CoercedInt, Color
from ledfx.configuration.plugin import TypedConfig
from ledfx.effects.audio import AudioAnalysisSource, AudioReactiveEffect
from ledfx.effects.utils.corsair import CORSAIR_CATEGORY, aio_layout
from ledfx.effects.utils.custom import (
    BeatLatch,
    FloatArray,
    Trigger,
    color_array,
    frame_step,
    volume_of,
)

# Coolant swirls this many turns a second when the music is quiet, and faster when loud
IDLE_TURNS = 0.15
LOUD_TURNS = 1.2
# Warming up, the coolant passes through violet rather than a muddy grey
WARM = color_array("#B000FF")


class PumpSwirl(AudioReactiveEffect):
    NAME = "Pump Swirl"
    CATEGORY = CORSAIR_CATEGORY

    class Config(AudioReactiveEffect.Config):
        cool_color: Color = Field(
            "#00A8FF", description="Color of the coolant when the music is calm"
        )
        hot_color: Color = Field(
            "#FF3000", description="Color of the coolant when the music is loud"
        )
        arms: CoercedInt = Field(
            2, description="Arms of the swirl in the pump", ge=1, le=4
        )
        heat_up: CoercedFloat = Field(
            0.5,
            description="How quickly the coolant heats up and cools down with the music",
            ge=0.05,
            le=3.0,
        )
        trigger: Trigger = Field(
            "Beat",
            description="Flash the radiator fans on the bass or on every percussive hit",
        )

    config = TypedConfig(Config)

    def on_activate(self, pixel_count: int) -> None:
        self._aio = aio_layout(pixel_count)
        self._turn = 0.0
        self.heat = 0.0
        self._volume = 0.0
        self._lows = 0.0
        self._flash = 0.0
        self._fan_turn = 0
        self._flashing = 0
        self._latch = BeatLatch()

    @override
    def config_updated(self, config: object) -> None:
        self._cool = color_array(self.config.cool_color)
        self._hot = color_array(self.config.hot_color)

    @override
    def audio_data_updated(self, data: AudioAnalysisSource) -> None:
        self._volume = volume_of(data)
        self._lows = float(data.lows_power())
        self._latch.listen(data, self.config.trigger)

    @override
    def render(self) -> None:
        dt = frame_step(self.passed)
        loud = min(1.0, self._volume * 2)
        # The coolant warms slowly with loud music and cools when it calms down
        self.heat += (loud - self.heat) * min(1.0, dt * self.config.heat_up)
        self._turn += dt * (IDLE_TURNS + LOUD_TURNS * loud)
        self._flash *= float(np.exp(-dt * 5))
        if self._latch.take(self.now):
            self._flash = 1.0
            # The fans take turns, the first one first
            self._flashing = self._fan_turn % 2
            self._fan_turn += 1

        aio = self._aio
        heat = self.heat
        if heat < 0.5:
            color = self._cool + (WARM - self._cool) * heat * 2
        else:
            color = WARM + (self._hot - WARM) * (heat - 0.5) * 2
        swirl = 0.5 + 0.5 * np.cos(
            2 * np.pi * (aio.angle - self._turn) * self.config.arms
        )
        pump: FloatArray = 0.35 + 0.65 * swirl**2
        # The radiator fans take turns flashing with the beat, and glow with the bass
        flashing = (aio.fan == self._flashing).astype(float)
        fans = 0.15 + 0.35 * min(1.0, self._lows * 1.5) + 0.5 * self._flash * flashing
        level = np.where(aio.pump, pump, fans)
        self.pixels = np.clip(color * level[:, None], 0, 255)
