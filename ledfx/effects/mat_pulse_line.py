import numpy as np
from pydantic import Field
from typing_extensions import override

from ledfx.configuration.fields import CoercedFloat, Color
from ledfx.configuration.plugin import TypedConfig
from ledfx.effects.utils.corsair import CorsairEffect, mat_layout
from ledfx.effects.utils.custom import FloatArray, color_array

# The trace's ink fades this fast, and the spike of a beat this fast
INK_FADE = 1.2
SPIKE_FADE = 12.0
# The flat line between beats
BASELINE = 0.35
WHITE = np.array((255.0, 255.0, 255.0))


class MatPulseLine(CorsairEffect):
    NAME = "Mat Pulse Line"

    class Config(CorsairEffect.Config):
        color: Color = Field("#00FF60", description="Color of the trace")
        beats_per_sweep: CoercedFloat = Field(
            4.0,
            description="Beats of the song for the trace to cross the pad",
            ge=1.0,
            le=16.0,
        )

    config = TypedConfig(Config)

    def on_activate(self, pixel_count: int) -> None:
        mat = mat_layout(pixel_count)
        self._along: FloatArray = mat.along
        self._mouse = mat.mouse
        # What the trace drew on each LED as it went past
        self._ink: FloatArray = np.zeros(pixel_count)
        self.pen = 0.0
        self._spike = 0.0

    @override
    def config_updated(self, config: object) -> None:
        self._color = color_array(self.config.color)

    @override
    def render(self) -> None:
        dt = self.step()
        self._ink *= float(np.exp(-dt * INK_FADE))
        self._spike *= float(np.exp(-dt * SPIKE_FADE))
        if self.beat():
            self._spike = 1.0
        # Like a heart monitor: the pen sweeps the pad from the left tip, writing a spike on each beat
        before = self.pen
        self.pen = (
            self.pen + self.song_moved() / self.config.beats_per_sweep + dt * 0.03
        ) % 1
        if self.pen >= before:
            under = (self._along >= before) & (self._along <= self.pen)
        else:
            under = (self._along >= before) | (self._along <= self.pen)
        under &= ~self._mouse
        signal = BASELINE + (1 - BASELINE) * self._spike
        self._ink[under] = np.maximum(self._ink[under], signal)
        ink = self._ink[:, None]
        # The spike burns white, the flat line in the trace's color
        pixels = (
            self._color * ink + (WHITE - self._color) * np.clip(ink - 0.6, 0, 1) * 2.5
        )
        # The mouse beeps on each beat
        mouse = WHITE * max(0.03, self._spike)
        self.pixels = np.clip(np.where(self._mouse[:, None], mouse, pixels), 0, 255)
