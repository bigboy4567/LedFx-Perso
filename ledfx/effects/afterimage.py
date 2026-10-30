import numpy as np
from pydantic import Field
from typing_extensions import override

from ledfx.configuration.fields import CoercedFloat
from ledfx.configuration.plugin import TypedConfig
from ledfx.effects.audio import AudioAnalysisSource, AudioReactiveEffect
from ledfx.effects.utils.custom import (
    CUSTOM_CATEGORY,
    BeatLatch,
    FloatArray,
    Trigger,
    frame_step,
    hue_colors,
)

# Flashes remembered at once; the oldest makes room
MAX_FLASHES = 4
# How bright the ghost of a flash appears, and how blurred its edges are
GHOST_LEVEL = 0.35
GHOST_BLUR = 0.03


class Afterimage(AudioReactiveEffect):
    NAME = "Afterimage"
    CATEGORY = CUSTOM_CATEGORY

    class Config(AudioReactiveEffect.Config):
        flash_time: CoercedFloat = Field(
            0.12, description="Seconds a flash of color lasts", ge=0.03, le=0.5
        )
        linger: CoercedFloat = Field(
            1.5, description="Seconds its afterimage lingers", ge=0.3, le=6.0
        )
        size: CoercedFloat = Field(
            0.3, description="Size of a flash, as a share of the strip", ge=0.05, le=1.0
        )
        trigger: Trigger = Field(
            "Beat", description="Flash on the bass or on every percussive hit"
        )

    config = TypedConfig(Config)

    def on_activate(self, pixel_count: int) -> None:
        self._u: FloatArray = np.arange(pixel_count) / max(pixel_count - 1, 1)
        self._centers: FloatArray = np.zeros(MAX_FLASHES)
        self._hues: FloatArray = np.zeros(MAX_FLASHES)
        self._ages: FloatArray = np.full(MAX_FLASHES, np.inf)
        self._latch = BeatLatch()

    @override
    def config_updated(self, config: object) -> None:
        if not hasattr(self, "_rng"):
            self._rng = np.random.default_rng()

    @override
    def audio_data_updated(self, data: AudioAnalysisSource) -> None:
        self._latch.listen(data, self.config.trigger)

    @override
    def render(self) -> None:
        self._ages += frame_step(self.passed)
        if self._latch.take(self.now):
            slot = int(np.argmax(self._ages))
            self._centers[slot] = self._rng.random()
            self._hues[slot] = self._rng.random()
            self._ages[slot] = 0.0

        pixels = np.zeros((self.pixel_count, 3))
        half = self.config.size / 2
        flash, linger = self.config.flash_time, self.config.linger
        for center, hue, age in zip(self._centers, self._hues, self._ages, strict=True):
            if age >= flash + linger:
                continue
            distance = np.abs(self._u - center)
            if age < flash:
                # The flash itself: a hard-edged block of saturated color
                color = hue_colors(np.array((hue,)))[0]
                shape = (distance <= half).astype(float)
            else:
                # Then the eye sees its opposite color, soft and fading
                color = hue_colors(np.array((hue + 0.5,)))[0] * GHOST_LEVEL
                color = color * float(np.exp(-(age - flash) / linger * 2.3))
                shape = np.clip((half - distance) / GHOST_BLUR + 0.5, 0, 1)
            np.maximum(pixels, color * shape[:, None], out=pixels)
        self.pixels = pixels
