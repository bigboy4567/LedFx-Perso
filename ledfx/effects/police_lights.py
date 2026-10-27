from typing import Literal

import numpy as np
from pydantic import Field
from typing_extensions import override

from ledfx.configuration.fields import CoercedInt, Color
from ledfx.configuration.plugin import TypedConfig
from ledfx.effects.audio import AudioAnalysisSource, AudioReactiveEffect
from ledfx.effects.utils.custom import (
    CUSTOM_CATEGORY,
    FloatArray,
    IntArray,
    color_array,
)

# Share of each beat taken by the burst of flashes, the rest stays dark
FLASH_WINDOW = 0.6

Mode = Literal["Flash", "Beacon"]


class PoliceLights(AudioReactiveEffect):
    NAME = "Police Lights"
    CATEGORY = CUSTOM_CATEGORY

    class Config(AudioReactiveEffect.Config):
        color_left: Color = Field("#FF0000", description="Color of the first light")
        color_right: Color = Field("#0040FF", description="Color of the second light")
        mode: Mode = Field(
            "Flash",
            description="Flash: the lights take turns on each beat. Beacon: a rotating light sweeps across",
        )
        flashes: CoercedInt = Field(
            3, description="Quick flashes in each burst (Flash mode)", ge=1, le=6
        )
        blocks: CoercedInt = Field(
            2,
            description="Number of blocks along the strip, alternating the two colors",
            ge=2,
            le=16,
        )

    config = TypedConfig(Config)

    def on_activate(self, pixel_count: int) -> None:
        self._layout(pixel_count)
        self._bar = 0.0

    def _layout(self, pixel_count: int) -> None:
        blocks = max(1, min(self.config.blocks, pixel_count))
        edges = np.linspace(0, pixel_count, blocks + 1).astype(int)
        # Which color each pixel belongs to: even blocks left, odd blocks right
        self._side: IntArray = np.repeat(np.arange(blocks) % 2, np.diff(edges))
        # Where each pixel sits inside its own block, 0 to 1
        within = [np.linspace(0, 1, width) for width in np.diff(edges)]
        self._within: FloatArray = np.concatenate(within)

    @override
    def config_updated(self, config: object) -> None:
        self._colors = np.stack(
            (color_array(self.config.color_left), color_array(self.config.color_right))
        )
        pixels = getattr(self, "pixels", None)
        if pixels is not None and hasattr(self, "_side"):
            self._layout(len(pixels))

    @override
    def audio_data_updated(self, data: AudioAnalysisSource) -> None:
        self._bar = float(data.bar_oscillator())

    @override
    def render(self) -> None:
        beat = int(self._bar)
        within_beat = self._bar % 1
        if self.config.mode == "Flash":
            # One side per beat, firing a quick burst at the start of the beat
            flashes = self.config.flashes
            step = int(within_beat / FLASH_WINDOW * flashes * 2)
            lit = within_beat < FLASH_WINDOW and step % 2 == 0
            level = np.where(self._side == beat % 2, float(lit), 0.0)
        else:
            # A beam turning once per beat: each block lights as it sweeps past
            beam = within_beat * 2 % 1
            distance = np.abs(self._within - beam)
            level = np.exp(-((distance / 0.2) ** 2))
            level *= self._side == (int(within_beat * 2) + beat) % 2
        self.pixels = self._colors[self._side] * level[:, None]
