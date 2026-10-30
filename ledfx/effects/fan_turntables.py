from typing import ClassVar

import numpy as np
from pydantic import Field
from typing_extensions import override

from ledfx.configuration.fields import CoercedFloat
from ledfx.configuration.plugin import TypedConfig
from ledfx.effects.gradient import GradientEffect
from ledfx.effects.utils.corsair import FAN_HUB, CorsairEffect, fan_layout, ring_gap
from ledfx.effects.utils.custom import FloatArray

# A scratch pulls the records back and forth for this long
SCRATCH = 0.25
# The sticker on each record, as a share of a turn
STICKER = 0.05
WHITE = np.array((255.0, 255.0, 255.0))


class FanTurntables(CorsairEffect, GradientEffect):
    NAME = "Fan Turntables"
    # Effect declares HIDDEN_KEYS = None, so every list override trips bad-override.
    HIDDEN_KEYS: ClassVar[list[str]] = ["gradient_roll"]  # pyrefly: ignore[bad-override]

    class Config(GradientEffect.Config):
        turns_per_beat: CoercedFloat = Field(
            0.25,
            description="Turns of the records per beat of the song",
            ge=0.05,
            le=1.0,
        )

    config = TypedConfig(Config)

    def on_activate(self, pixel_count: int) -> None:
        self._fans = fan_layout(pixel_count)
        # Each record's turn, and how long ago it was last scratched
        self.turns: FloatArray = self._rng.random(self._fans.count)
        self._scratched: FloatArray = np.full(self._fans.count, np.inf)

    @override
    def render(self) -> None:
        dt = self.step()
        fans = self._fans
        self._scratched += dt
        # Each percussive hit scratches one of the records
        if self.hit():
            self._scratched[self._rng.integers(fans.count)] = 0.0
        spin = np.full(
            fans.count, self.song_moved() * self.config.turns_per_beat + dt * 0.1
        )
        scratching = self._scratched < SCRATCH
        # A scratch drags the record back and forth, fast
        spin[scratching] = (
            np.sin(self._scratched[scratching] / SCRATCH * 2 * np.pi) * dt * 3
        )
        self.turns += spin
        turn = self.turns[fans.fan]
        # Fine grooves shimmer round the rim; the sticker turns with the record
        grooves = 0.08 + 0.06 * np.cos(2 * np.pi * (fans.angle - turn) * 6)
        sticker = ring_gap(fans.angle, turn) < STICKER
        level = np.where(sticker, 1.0, grooves) * (0.5 + 0.5 * self.loudness)
        rim = WHITE * level[:, None]
        # The hub is the record's label, in its own color
        label = self.get_gradient_color_vectorized1d(
            fans.fan / max(fans.count - 1, 1) * 0.999
        )
        self.pixels = np.where((fans.ring == FAN_HUB)[:, None], label * 0.8, rim)
