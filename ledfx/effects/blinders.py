from typing import Literal

import numpy as np
from pydantic import Field
from typing_extensions import override

from ledfx.configuration.fields import CoercedFloat, CoercedInt
from ledfx.configuration.plugin import TypedConfig
from ledfx.effects.audio import AudioAnalysisSource, AudioReactiveEffect
from ledfx.effects.utils.custom import (
    CUSTOM_CATEGORY,
    BeatLatch,
    FloatArray,
    IntArray,
    PeakTracker,
    Trigger,
    color_array,
    frame_step,
    segment_widths,
)

# A tungsten blinder burns warm white, and its filament reddens as it cools
HOT = color_array("#FFDDB0")
COOLING = color_array("#FF5A08")
# Each blinder holds two lamps, here, as shares of its space
LAMPS = (0.3, 0.7)
LAMP_WIDTH = 0.12

Pattern = Literal["All", "Alternate", "Chase"]


class Blinders(AudioReactiveEffect):
    NAME = "Blinders"
    CATEGORY = CUSTOM_CATEGORY

    class Config(AudioReactiveEffect.Config):
        blinders: CoercedInt = Field(
            4, description="Blinders along the strip", ge=1, le=16
        )
        pattern: Pattern = Field(
            "Alternate",
            description="Fire all blinders together, every other one in turn, or one after another",
        )
        cool_down: CoercedFloat = Field(
            1.0, description="Seconds the filaments take to cool down", ge=0.2, le=4.0
        )
        threshold: CoercedFloat = Field(
            0.6,
            description="How strong the bass must be, for this song, to fire the blinders",
            ge=0.0,
            le=1.0,
        )
        trigger: Trigger = Field(
            "Beat", description="Fire on the bass or on every percussive hit"
        )

    config = TypedConfig(Config)

    def on_activate(self, pixel_count: int) -> None:
        self._layout(pixel_count)
        self._fired = 0
        self._lows = 0.0
        self._peaks = PeakTracker(1)
        self._latch = BeatLatch()

    def _layout(self, pixel_count: int) -> None:
        widths = segment_widths(pixel_count, self.config.blinders)
        count = widths.size
        self._blinder: IntArray = np.repeat(np.arange(count), widths)
        starts = np.cumsum(widths) - widths
        within = (np.arange(pixel_count) - starts[self._blinder] + 0.5) / widths[
            self._blinder
        ]
        lamps = [np.exp(-(((within - at) / LAMP_WIDTH) ** 2)) for at in LAMPS]
        self._shape: FloatArray = np.maximum(*lamps)
        self._shape[widths[self._blinder] < 4] = 1.0
        self._levels: FloatArray = np.zeros(count)

    @override
    def config_updated(self, config: object) -> None:
        pixels = getattr(self, "pixels", None)
        if pixels is not None and hasattr(self, "_levels"):
            self._layout(len(pixels))

    @override
    def audio_data_updated(self, data: AudioAnalysisSource) -> None:
        level = self._peaks.update(np.array((float(data.lows_power()),)))
        self._lows = float(level[0])
        self._latch.listen(data, self.config.trigger)

    def _fire(self) -> None:
        count = self._levels.size
        match self.config.pattern:
            case "All":
                chosen = np.arange(count)
            case "Alternate":
                chosen = np.arange(self._fired % 2, count, 2)
            case "Chase":
                chosen = np.array([self._fired % count])
        self._levels[chosen] = 1.0
        self._fired += 1

    @override
    def render(self) -> None:
        self._levels *= float(
            np.exp(-frame_step(self.passed) * 3 / self.config.cool_down)
        )
        if self._latch.take(self.now) and self._lows >= self.config.threshold:
            self._fire()

        levels = self._levels[:, None]
        colors = COOLING + (HOT - COOLING) * np.sqrt(levels)
        self.pixels = (colors * levels)[self._blinder] * self._shape[:, None]
