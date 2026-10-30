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
)

# The arc widens from this to that share of the strip as it climbs
NARROW, WIDE = 0.02, 0.14
# At the top the arc breaks with a pop this long
POP_TIME = 0.25
# The rails glow faintly between arcs
RAILS = 0.05
WHITE = np.array((255.0, 255.0, 255.0))


class JacobsLadder(AudioReactiveEffect):
    NAME = "Jacob's Ladder"
    CATEGORY = CUSTOM_CATEGORY

    class Config(AudioReactiveEffect.Config):
        color: Color = Field("#B08CFF", description="Color of the arc")
        climb_time: CoercedFloat = Field(
            1.5, description="Seconds an arc takes to climb the strip", ge=0.3, le=6.0
        )
        crackle: CoercedFloat = Field(
            0.6, description="How much the treble makes the arc crackle", ge=0.0, le=1.0
        )
        trigger: Trigger = Field(
            "Beat", description="Flare the arc on the bass or on every percussive hit"
        )

    config = TypedConfig(Config)

    def on_activate(self, pixel_count: int) -> None:
        self._u: FloatArray = np.arange(pixel_count) / max(pixel_count - 1, 1)
        self.height = 0.0
        self._pop = 0.0
        self._flare = 0.0
        self._highs = 0.0
        self._latch = BeatLatch()

    @override
    def config_updated(self, config: object) -> None:
        if not hasattr(self, "_rng"):
            self._rng = np.random.default_rng()
        self._color = color_array(self.config.color)

    @override
    def audio_data_updated(self, data: AudioAnalysisSource) -> None:
        self._highs = float(data.high_power())
        self._latch.listen(data, self.config.trigger)

    @override
    def render(self) -> None:
        dt = frame_step(self.passed)
        self._pop = max(0.0, self._pop - dt)
        self._flare *= float(np.exp(-dt * 6))
        if self._latch.take(self.now):
            self._flare = 1.0
        # Hot air carries the arc up, faster the higher it gets
        self.height += dt / self.config.climb_time * (0.4 + 1.2 * self.height)
        if self.height >= 1:
            self.height = 0.0
            self._pop = POP_TIME

        n = self.pixel_count
        width = NARROW + (WIDE - NARROW) * self.height
        inside = np.clip(1 - np.abs(self._u - self.height) / width, 0, 1)
        # A plasma arc is ragged and restless, more so with the treble
        ragged = self._rng.uniform(
            1 - 0.5 * (0.3 + self.config.crackle * self._highs), 1, n
        )
        level = np.maximum(RAILS, inside**0.5 * ragged * (0.7 + 0.5 * self._flare))
        pixels = self._color * np.clip(level, 0, 1)[:, None]
        hot = (np.clip(level - 0.8, 0, 1) * 4)[:, None]
        pixels = pixels + (WHITE - pixels) * hot
        if self._pop:
            pixels = pixels + (WHITE - pixels) * (self._pop / POP_TIME) * 0.7
        self.pixels = np.clip(pixels, 0, 255)
