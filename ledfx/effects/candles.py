import numpy as np
from pydantic import Field
from typing_extensions import override

from ledfx.configuration.fields import CoercedFloat, CoercedInt, Color
from ledfx.configuration.plugin import TypedConfig
from ledfx.effects.audio import AudioAnalysisSource, AudioReactiveEffect
from ledfx.effects.utils.custom import (
    CUSTOM_CATEGORY,
    BeatLatch,
    FloatArray,
    IntArray,
    color_array,
    frame_step,
    segment_widths,
    volume_of,
)

# A flame picks a new brightness to drift toward this often, per second
FLICKER_RATE = 12.0
# Width of a flame, as a share of the space of its candle
FLAME_WIDTH = 0.3
# The hot heart of a flame turns this pale
CORE = np.array((255.0, 235.0, 200.0))


class Candles(AudioReactiveEffect):
    NAME = "Candles"
    CATEGORY = CUSTOM_CATEGORY

    class Config(AudioReactiveEffect.Config):
        candles: CoercedInt = Field(6, description="How many candles", ge=1, le=30)
        color: Color = Field("#FF8A1E", description="Color of the flames")
        flicker: CoercedFloat = Field(
            0.5, description="How restless the flames are in still air", ge=0.0, le=1.0
        )
        draft: CoercedFloat = Field(
            1.0,
            description="How much loud music makes the flames waver, as if blown on",
            ge=0.0,
            le=3.0,
        )
        beat_flare: bool = Field(True, description="Flare the flames up on each beat")

    config = TypedConfig(Config)

    def on_activate(self, pixel_count: int) -> None:
        self._layout(pixel_count)
        self._volume = 0.0
        self._latch = BeatLatch()

    def _layout(self, pixel_count: int) -> None:
        widths = segment_widths(pixel_count, self.config.candles)
        count = widths.size
        self._candle: IntArray = np.repeat(np.arange(count), widths)
        starts = np.cumsum(widths) - widths
        within = np.arange(pixel_count) - starts[self._candle]
        center = (widths[self._candle] - 1) / 2
        spread = np.maximum(widths[self._candle] * FLAME_WIDTH, 0.6)
        self._shape: FloatArray = np.exp(-(((within - center) / spread) ** 2))
        self._levels: FloatArray = np.full(count, 0.8)
        self._targets: FloatArray = np.full(count, 0.8)

    @override
    def config_updated(self, config: object) -> None:
        if not hasattr(self, "_rng"):
            self._rng = np.random.default_rng()
        self._color = color_array(self.config.color)
        pixels = getattr(self, "pixels", None)
        if pixels is not None and hasattr(self, "_levels"):
            self._layout(len(pixels))

    @override
    def audio_data_updated(self, data: AudioAnalysisSource) -> None:
        self._volume = volume_of(data)
        self._latch.listen(data, "Beat")

    @override
    def render(self) -> None:
        dt = frame_step(self.passed)
        count = self._levels.size
        unrest = min(
            1.0, self.config.flicker * 0.4 + self.config.draft * self._volume * 0.5
        )
        changing = self._rng.random(count) < dt * FLICKER_RATE
        self._targets[changing] = 1 - unrest * self._rng.random(int(changing.sum()))
        if self._latch.take(self.now) and self.config.beat_flare:
            self._levels[:] = np.minimum(self._levels + 0.35, 1.3)
        self._levels += (self._targets - self._levels) * min(1.0, dt * 15)

        level = self._shape * self._levels[self._candle]
        # Bright flames burn paler at the heart, dim ones redden
        heat = np.clip(level - 0.6, 0, 1)[:, None]
        pixels = self._color * level[:, None] + (CORE - self._color) * heat
        self.pixels = np.clip(pixels, 0, 255)
