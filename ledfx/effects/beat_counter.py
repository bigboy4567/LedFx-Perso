from typing import Literal

import numpy as np
from pydantic import Field
from typing_extensions import override

from ledfx.configuration.fields import CoercedInt, Color
from ledfx.configuration.plugin import TypedConfig
from ledfx.effects.audio import AudioAnalysisSource, AudioReactiveEffect
from ledfx.effects.utils.custom import (
    CUSTOM_CATEGORY,
    BeatLatch,
    FloatArray,
    IntArray,
    Trigger,
    color_array,
    frame_step,
    segment_widths,
)

# Brightness of a bit at zero, so the counter stays readable
OFF_LEVEL = 0.06
# How fast the white flash of a bit that just changed fades
CHANGE_DECAY = 8.0

Code = Literal["Binary", "Gray"]


class BeatCounter(AudioReactiveEffect):
    NAME = "Beat Counter"
    CATEGORY = CUSTOM_CATEGORY

    class Config(AudioReactiveEffect.Config):
        bits: CoercedInt = Field(
            8, description="Bits of the counter along the strip", ge=2, le=16
        )
        color: Color = Field("#00E5FF", description="Color of a bit at one")
        code: Code = Field(
            "Binary",
            description="Binary: plain counting. Gray: only one bit changes on each beat",
        )
        gap: bool = Field(True, description="Leave a dark pixel between the bits")
        trigger: Trigger = Field(
            "Beat", description="Count the bass beats or every percussive hit"
        )

    config = TypedConfig(Config)

    def on_activate(self, pixel_count: int) -> None:
        self._layout(pixel_count)
        self._count = 0
        self._latch = BeatLatch()

    def _layout(self, pixel_count: int) -> None:
        widths = segment_widths(pixel_count, self.config.bits)
        self._bit: IntArray = np.repeat(np.arange(widths.size), widths)
        # The last pixel of each wide enough bit stays dark as a separator
        ends = np.cumsum(widths) - 1
        self._separator = np.zeros(pixel_count, dtype=bool)
        self._separator[ends[widths >= 3]] = True
        self._changed: FloatArray = np.zeros(widths.size)

    @override
    def config_updated(self, config: object) -> None:
        self._color = color_array(self.config.color)
        pixels = getattr(self, "pixels", None)
        if pixels is not None and hasattr(self, "_changed"):
            self._layout(len(pixels))

    @override
    def audio_data_updated(self, data: AudioAnalysisSource) -> None:
        self._latch.listen(data, self.config.trigger)

    def _bits(self, count: int) -> IntArray:
        value = count ^ (count >> 1) if self.config.code == "Gray" else count
        # The first bit along the strip is the lowest
        return (value >> np.arange(self._changed.size)) & 1

    @override
    def render(self) -> None:
        self._changed *= float(np.exp(-frame_step(self.passed) * CHANGE_DECAY))
        if self._latch.take(self.now):
            before = self._bits(self._count)
            self._count = (self._count + 1) % (1 << self._changed.size)
            self._changed[self._bits(self._count) != before] = 1.0

        bits = self._bits(self._count)
        level = np.where(bits == 1, 1.0, OFF_LEVEL)[self._bit]
        flash = self._changed[self._bit][:, None]
        pixels = self._color * level[:, None]
        pixels += (255 - pixels) * flash * 0.7
        if self.config.gap:
            pixels[self._separator] = 0
        self.pixels = np.clip(pixels, 0, 255)
