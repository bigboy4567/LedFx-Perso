from typing import Literal

import numpy as np
from pydantic import Field
from typing_extensions import override

from ledfx.configuration.fields import CoercedFloat, Color
from ledfx.configuration.plugin import TypedConfig
from ledfx.effects.audio import AudioAnalysisSource, AudioReactiveEffect
from ledfx.effects.utils.custom import (
    CUSTOM_CATEGORY,
    HAT,
    KICK,
    SNARE,
    FloatArray,
    HitClassifier,
    IntArray,
    color_array,
    frame_step,
)

# Which drum each pad plays, from the start of the strip
LAYOUTS = {
    "Kick, snare, hi-hat": (KICK, SNARE, HAT),
    "Snare, kick, hi-hat": (SNARE, KICK, HAT),
    "Hi-hat, kick, snare": (HAT, KICK, SNARE),
}
Layout = Literal["Kick, snare, hi-hat", "Snare, kick, hi-hat", "Hi-hat, kick, snare"]


class DrumPads(AudioReactiveEffect):
    NAME = "Drum Pads"
    CATEGORY = CUSTOM_CATEGORY

    class Config(AudioReactiveEffect.Config):
        kick_color: Color = Field("#FF3030", description="Color of the kick drum pad")
        snare_color: Color = Field("#FFD000", description="Color of the snare pad")
        hat_color: Color = Field("#30C8FF", description="Color of the hi-hat pad")
        layout: Layout = Field(
            "Kick, snare, hi-hat", description="Order of the pads along the strip"
        )
        decay: CoercedFloat = Field(
            6.0, description="How fast a pad fades after a hit", ge=1.0, le=20.0
        )

    config = TypedConfig(Config)

    def on_activate(self, pixel_count: int) -> None:
        pads = min(3, pixel_count)
        edges = np.linspace(0, pixel_count, pads + 1).astype(int)
        self._widths: IntArray = np.diff(edges)
        # Each pad is brightest in its middle, like a lit drum skin
        self._shape: FloatArray = np.concatenate(
            [0.6 + 0.4 * np.sin(np.pi * (np.arange(w) + 0.5) / w) for w in self._widths]
        )
        self._levels: FloatArray = np.zeros(3)
        self._drums = HitClassifier()
        self._hit: int | None = None

    @override
    def config_updated(self, config: object) -> None:
        self._colors = np.stack(
            [
                color_array(self.config.kick_color),
                color_array(self.config.snare_color),
                color_array(self.config.hat_color),
            ]
        )

    @override
    def audio_data_updated(self, data: AudioAnalysisSource) -> None:
        drum = self._drums.listen(data)
        if drum is not None:
            self._hit = drum

    @override
    def render(self) -> None:
        self._levels *= float(np.exp(-frame_step(self.passed) * self.config.decay))
        if self._hit is not None:
            self._levels[self._hit] = 1.0
            self._hit = None
        hits = self._colors * self._levels[:, None]
        if self._widths.size < len(self._levels):
            # Too few pixels for a pad each: every pixel shows whichever drum is lit
            lit = np.tile(hits.max(axis=0), (self._widths.size, 1))
        else:
            lit = hits[np.array(LAYOUTS[self.config.layout])]
        self.pixels = np.repeat(lit, self._widths, axis=0) * self._shape[:, None]
