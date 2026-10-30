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
    TempoTracker,
    color_array,
    frame_step,
)

SUN = color_array("#FFF2B8")
CORONA = color_array("#FFB860")
WHITE = np.array((255.0, 255.0, 255.0))
# The corona fades over this share of the strip beyond the sun's edge
CORONA_REACH = 0.08
# The moon is a touch bigger than the sun, so totality hides it all
MOON_SIZE = 1.03


class Eclipse(AudioReactiveEffect):
    NAME = "Eclipse"
    CATEGORY = CUSTOM_CATEGORY

    class Config(AudioReactiveEffect.Config):
        passage: CoercedInt = Field(
            8, description="Bars of the song for the moon to cross the sun", ge=1, le=64
        )
        sun_size: CoercedFloat = Field(
            0.3,
            description="Width of the sun, as a share of the strip",
            ge=0.05,
            le=0.8,
        )
        flares: bool = Field(True, description="The corona flares on each beat")

    config = TypedConfig(Config)

    def on_activate(self, pixel_count: int) -> None:
        self._u: FloatArray = np.arange(pixel_count) / max(pixel_count - 1, 1)
        self._flare = 0.0
        self._tempo = TempoTracker()
        self._latch = BeatLatch()

    @override
    def audio_data_updated(self, data: AudioAnalysisSource) -> None:
        self._tempo.listen(data)
        self._latch.listen(data, "Beat")

    def moon_at(self) -> float:
        """Where the moon is along the strip: it crosses from well left of the sun to well right."""
        radius = self.config.sun_size / 2
        progress = (self._tempo.beats / (4 * self.config.passage)) % 1
        return 0.5 - 3 * radius + progress * 6 * radius

    @override
    def render(self) -> None:
        dt = frame_step(self.passed)
        self._flare *= float(np.exp(-dt * 3))
        if self._latch.take(self.now) and self.config.flares:
            self._flare = 1.0

        u = self._u
        radius = self.config.sun_size / 2
        from_sun = np.abs(u - 0.5)
        sun = from_sun <= radius
        moon = np.abs(u - self.moon_at()) <= radius * MOON_SIZE
        showing = sun & ~moon
        covered = 1 - showing.sum() / max(int(sun.sum()), 1)
        # The corona shows as the sun's face is hidden, and leaps with the flares
        corona = np.exp(-np.clip(from_sun - radius, 0, None) / CORONA_REACH) * (~sun)
        corona_level = (0.15 + 0.85 * covered) * (0.6 + 0.4 * self._flare)
        pixels = CORONA * (corona * corona_level)[:, None]
        # The last sliver before totality blazes like a diamond ring
        blaze = covered**8
        face = SUN + (WHITE - SUN) * blaze
        pixels[showing] = face
        pixels[sun & moon] = CORONA * 0.06 * covered
        self.pixels = np.clip(pixels, 0, 255)
