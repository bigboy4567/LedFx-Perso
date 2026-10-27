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
    color_array,
    frame_step,
    splat,
)

# Share of the swarm that lights up together on a beat
BEAT_FLASH_SHARE = 0.3


class Fireflies(AudioReactiveEffect):
    NAME = "Fireflies"
    CATEGORY = CUSTOM_CATEGORY

    class Config(AudioReactiveEffect.Config):
        count: CoercedInt = Field(20, description="How many fireflies", ge=1, le=100)
        color: Color = Field("#B4FF3C", description="Color of the fireflies")
        size: CoercedFloat = Field(
            1.5, description="Glow radius of a firefly, in pixels", ge=0.5, le=6.0
        )
        drift: CoercedFloat = Field(
            0.5, description="How much the fireflies wander", ge=0.0, le=2.0
        )
        beat_flash: bool = Field(
            True, description="Light up part of the swarm together on each beat"
        )

    config = TypedConfig(Config)

    def on_activate(self, pixel_count: int) -> None:
        self._x: FloatArray = np.arange(pixel_count, dtype=float)
        self._scatter(pixel_count)
        self._mids = 0.0
        self._latch = BeatLatch()

    def _scatter(self, pixel_count: int) -> None:
        count = self.config.count
        self._pos: FloatArray = self._rng.uniform(0, max(pixel_count - 1, 0), count)
        self._vel: FloatArray = self._rng.normal(0, 1, count)
        self._phase: FloatArray = self._rng.uniform(0, 2 * np.pi, count)
        # Each firefly keeps its own rhythm, a blink every one to three seconds
        self._rate: FloatArray = self._rng.uniform(2.0, 6.0, count)

    @override
    def config_updated(self, config: object) -> None:
        if not hasattr(self, "_rng"):
            self._rng = np.random.default_rng()
        self._color = color_array(self.config.color)
        pixels = getattr(self, "pixels", None)
        if (
            pixels is not None
            and hasattr(self, "_pos")
            and self._pos.size != self.config.count
        ):
            self._scatter(len(pixels))

    @override
    def audio_data_updated(self, data: AudioAnalysisSource) -> None:
        self._mids = float(data.mids_power())
        self._latch.listen(data, "Beat")

    @override
    def render(self) -> None:
        n = self.pixel_count
        dt = frame_step(self.passed)
        # Mids wake the swarm up: faster blinking
        self._phase += dt * self._rate * (1 + 2 * self._mids)
        if self._latch.take(self.now) and self.config.beat_flash:
            flashing = self._rng.random(self._phase.size) < BEAT_FLASH_SHARE
            self._phase[flashing] = 0.0
        # Wander with a slowly changing heading, turning back at the ends
        self._vel += self._rng.normal(0, 1, self._vel.size) * dt * 2
        np.clip(self._vel, -1.5, 1.5, out=self._vel)
        self._pos += self._vel * self.config.drift * dt * 3
        outside = (self._pos < 0) | (self._pos > n - 1)
        self._vel[outside] *= -1
        np.clip(self._pos, 0, max(n - 1, 0), out=self._pos)

        # A sharp blink with a long dark rest, like a real firefly
        glow = (0.5 + 0.5 * np.cos(self._phase)) ** 6
        level = np.zeros(n)
        for pos, amount in zip(self._pos, glow, strict=True):
            splat(level, self._x, float(pos), self.config.size, float(amount))
        self.pixels = self._color * level[:, None]
