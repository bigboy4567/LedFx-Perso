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
    TempoTracker,
    frame_step,
    hue_colors,
    segment_widths,
)

# The looks a lighting operator moves between
LOOKS = ("solid", "split", "spread", "alternate")
# A PAR can lights its own space, spilling a little onto its neighbours
BEAM_EDGE = 0.25


class StageWash(AudioReactiveEffect):
    NAME = "Stage Wash"
    CATEGORY = CUSTOM_CATEGORY

    class Config(AudioReactiveEffect.Config):
        cans: CoercedInt = Field(8, description="PAR cans along the strip", ge=2, le=32)
        bars: CoercedInt = Field(
            2, description="Bars of the song before the next look", ge=1, le=16
        )
        fade: CoercedFloat = Field(
            1.0, description="Seconds to cross-fade to the next look", ge=0.1, le=6.0
        )
        bump: CoercedFloat = Field(
            0.3, description="How much the cans bump up on each beat", ge=0.0, le=1.0
        )

    config = TypedConfig(Config)

    def on_activate(self, pixel_count: int) -> None:
        self._layout(pixel_count)
        self._look = -1
        self._progress = 1.0
        self._bump = 0.0
        self._tempo = TempoTracker()
        self._latch = BeatLatch()

    def _layout(self, pixel_count: int) -> None:
        widths = segment_widths(pixel_count, self.config.cans)
        count = widths.size
        self._can: IntArray = np.repeat(np.arange(count), widths)
        starts = np.cumsum(widths) - widths
        within = (np.arange(pixel_count) - starts[self._can] + 0.5) / widths[self._can]
        edge = np.minimum(within, 1 - within)
        self._shape: FloatArray = 0.4 + 0.6 * np.clip(edge / BEAM_EDGE, 0, 1)
        self._from: FloatArray = np.zeros((count, 3))
        self._to: FloatArray = np.zeros((count, 3))

    @override
    def config_updated(self, config: object) -> None:
        if not hasattr(self, "_rng"):
            self._rng = np.random.default_rng()
        pixels = getattr(self, "pixels", None)
        if pixels is not None and hasattr(self, "_to"):
            self._layout(len(pixels))

    @override
    def audio_data_updated(self, data: AudioAnalysisSource) -> None:
        self._tempo.listen(data)
        self._latch.listen(data, "Beat")

    def new_look(self) -> FloatArray:
        count = self._to.shape[0]
        hue = float(self._rng.random())
        index = np.arange(count)
        match LOOKS[int(self._rng.integers(len(LOOKS)))]:
            case "solid":
                hues = np.full(count, hue)
            case "split":
                hues = np.where(index < count / 2, hue, hue + 0.5)
            case "spread":
                hues = hue + index / count * 0.6
            case _:
                hues = np.where(index % 2 == 0, hue, hue + 0.33)
        return hue_colors(hues)

    def colors(self) -> FloatArray:
        eased = self._progress * self._progress * (3 - 2 * self._progress)
        return self._from + (self._to - self._from) * eased

    @override
    def render(self) -> None:
        dt = frame_step(self.passed)
        look = int(self._tempo.beats // (4 * self.config.bars))
        if look != self._look:
            self._look = look
            self._from = self.colors()
            self._to = self.new_look()
            self._progress = 0.0
        self._progress = min(1.0, self._progress + dt / self.config.fade)
        self._bump *= float(np.exp(-dt * 6))
        if self._latch.take(self.now):
            self._bump = 1.0

        level = 1 - self.config.bump * (1 - self._bump)
        self.pixels = self.colors()[self._can] * (self._shape * level)[:, None]
