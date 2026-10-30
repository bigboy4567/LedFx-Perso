import numpy as np
from pydantic import Field
from typing_extensions import override

from ledfx.configuration.fields import CoercedFloat, Color
from ledfx.configuration.plugin import TypedConfig
from ledfx.effects.audio import AudioAnalysisSource, AudioReactiveEffect
from ledfx.effects.utils.custom import (
    CUSTOM_CATEGORY,
    BeatLatch,
    FloatArray,
    Trigger,
    color_array,
    frame_step,
    volume_of,
)

# Ordered dithering: a repeating ladder of thresholds turns shades into on and off pixels
BAYER = (np.array((0, 4, 2, 6, 1, 5, 3, 7)) + 0.5) / 8


class Dither(AudioReactiveEffect):
    NAME = "Dither"
    CATEGORY = CUSTOM_CATEGORY

    class Config(AudioReactiveEffect.Config):
        ink: Color = Field("#00FF9C", description="Color of the lit pixels")
        paper: Color = Field("#001A10", description="Color of the unlit pixels")
        wave_size: CoercedFloat = Field(
            0.3,
            description="Length of the waves of shade, as a share of the strip",
            ge=0.02,
            le=1.0,
        )
        speed: CoercedFloat = Field(
            0.4, description="How fast the waves move", ge=0.0, le=3.0
        )
        trigger: Trigger = Field(
            "Beat",
            description="Swap ink and paper on the bass or on every percussive hit",
        )

    config = TypedConfig(Config)

    def on_activate(self, pixel_count: int) -> None:
        self._u: FloatArray = np.arange(pixel_count) / max(pixel_count - 1, 1)
        self._threshold: FloatArray = BAYER[np.arange(pixel_count) % len(BAYER)]
        self._phase = 0.0
        self.inverted = False
        self._volume = 0.0
        self._latch = BeatLatch()

    @override
    def config_updated(self, config: object) -> None:
        self._ink = color_array(self.config.ink)
        self._paper = color_array(self.config.paper)

    @override
    def audio_data_updated(self, data: AudioAnalysisSource) -> None:
        self._volume = volume_of(data)
        self._latch.listen(data, self.config.trigger)

    def shade(self) -> FloatArray:
        wave = 0.5 + 0.5 * np.sin(
            2 * np.pi * (self._u / self.config.wave_size - self._phase)
        )
        return wave * (0.3 + 0.7 * min(1.0, self._volume * 2))

    @override
    def render(self) -> None:
        self._phase += frame_step(self.passed) * self.config.speed
        if self._latch.take(self.now):
            self.inverted = not self.inverted
        lit = self.shade() > self._threshold
        if self.inverted:
            lit = ~lit
        self.pixels = np.where(lit[:, None], self._ink, self._paper)
