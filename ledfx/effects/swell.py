from typing import ClassVar, Literal

import numpy as np
from pydantic import Field
from typing_extensions import override

from ledfx.configuration.fields import CoercedFloat
from ledfx.configuration.plugin import TypedConfig
from ledfx.effects.audio import AudioAnalysisSource, AudioReactiveEffect
from ledfx.effects.gradient import GradientEffect
from ledfx.effects.utils.custom import (
    CUSTOM_CATEGORY,
    FloatArray,
    TempoTracker,
)

LENGTHS = {"1 beat": 1, "2 beats": 2, "1 bar": 4}
# Width of the soft front of the swell, as a share of the strip
EDGE = 0.06
# Share of a beat the white cut lasts after the downbeat
CUT = 0.125
WHITE = np.array((255.0, 255.0, 255.0))

Length = Literal["1 beat", "2 beats", "1 bar"]


class Swell(AudioReactiveEffect, GradientEffect):
    NAME = "Swell"
    CATEGORY = CUSTOM_CATEGORY
    # Effect declares HIDDEN_KEYS = None, so every list override trips bad-override.
    HIDDEN_KEYS: ClassVar[list[str]] = ["gradient_roll"]  # pyrefly: ignore[bad-override]

    class Config(GradientEffect.Config):
        length: Length = Field(
            "1 beat", description="How long each swell builds before it is cut"
        )
        curve: CoercedFloat = Field(
            3.0,
            description="How late in the swell the light rushes in, like a reversed cymbal",
            ge=1.0,
            le=6.0,
        )
        from_center: bool = Field(
            True, description="Swell out from the middle, or along from the start"
        )

    config = TypedConfig(Config)

    def on_activate(self, pixel_count: int) -> None:
        self._u: FloatArray = np.arange(pixel_count) / max(pixel_count - 1, 1)
        self._tempo = TempoTracker()

    @override
    def audio_data_updated(self, data: AudioAnalysisSource) -> None:
        self._tempo.listen(data)

    def rise(self) -> tuple[float, float]:
        """How far the swell has built, and how far into it the song is, both 0 to 1."""
        length = LENGTHS[self.config.length]
        into = (self._tempo.beats / length) % 1
        return into**self.config.curve, into

    @override
    def render(self) -> None:
        rise, into = self.rise()
        u = self._u
        reach = np.abs(u - 0.5) * 2 if self.config.from_center else u
        inside = np.clip((rise - reach) / EDGE + 1, 0, 1)
        colors = self.get_gradient_color_vectorized1d(u)
        pixels = colors * (inside * (0.1 + 0.9 * rise))[:, None]
        # The swell is cut on the beat it was building to, with a white tick
        cut = max(0.0, 1 - into * LENGTHS[self.config.length] / CUT)
        self.pixels = pixels + (WHITE - pixels) * cut * 0.5
