import numpy as np
from pydantic import Field
from typing_extensions import override

from ledfx.configuration.fields import CoercedFloat, CoercedInt, Color
from ledfx.configuration.plugin import TypedConfig
from ledfx.effects.audio import AudioAnalysisSource, AudioReactiveEffect
from ledfx.effects.utils.custom import (
    CUSTOM_CATEGORY,
    FloatArray,
    TempoTracker,
    color_array,
    frame_step,
    volume_of,
)

# How quickly a strobe flash fades
FLASH_DECAY = 12.0
# How sharp the spokes are: the higher, the thinner
SPOKE_POWER = 4


class WagonWheel(AudioReactiveEffect):
    NAME = "Wagon Wheel"
    CATEGORY = CUSTOM_CATEGORY

    class Config(AudioReactiveEffect.Config):
        color: Color = Field("#FFFFFF", description="Color of the spokes")
        spokes: CoercedInt = Field(8, description="Spokes along the strip", ge=2, le=40)
        spin: CoercedFloat = Field(
            6.0,
            description="How fast the wheel spins, in spokes per second",
            ge=0.5,
            le=40.0,
        )
        flashes_per_beat: CoercedInt = Field(
            4, description="Strobe flashes per beat of the song", ge=1, le=8
        )

    config = TypedConfig(Config)

    def on_activate(self, pixel_count: int) -> None:
        self._u: FloatArray = np.arange(pixel_count) / max(pixel_count - 1, 1)
        # Where the spokes really are, and where they were when the strobe last fired
        self.turned = 0.0
        self.seen = 0.0
        self._flash_count = -1
        self._level = 0.0
        self._volume = 0.0
        self._tempo = TempoTracker()

    @override
    def config_updated(self, config: object) -> None:
        self._color = color_array(self.config.color)

    @override
    def audio_data_updated(self, data: AudioAnalysisSource) -> None:
        self._tempo.listen(data)
        self._volume = volume_of(data)

    @override
    def render(self) -> None:
        dt = frame_step(self.passed)
        # The wheel spins faster with the music; the strobe keeps time with the song,
        # so the spokes seem to crawl, stand still or turn backwards
        self.turned += dt * self.config.spin * (0.5 + 2 * self._volume)
        self._level *= float(np.exp(-dt * FLASH_DECAY))
        flashes = int(self._tempo.beats * self.config.flashes_per_beat)
        if flashes != self._flash_count:
            self._flash_count = flashes
            self.seen = self.turned
            self._level = 1.0

        spokes = (
            0.5 + 0.5 * np.cos(2 * np.pi * (self._u * self.config.spokes - self.seen))
        ) ** SPOKE_POWER
        self.pixels = self._color * (spokes * self._level)[:, None]
