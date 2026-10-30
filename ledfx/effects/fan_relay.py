from typing import ClassVar

import numpy as np
from pydantic import Field
from typing_extensions import override

from ledfx.configuration.fields import CoercedFloat
from ledfx.configuration.plugin import TypedConfig
from ledfx.effects.gradient import GradientEffect
from ledfx.effects.utils.corsair import FAN_HUB, FAN_RIM, CorsairEffect, fan_layout

# The runner's trail, as a share of a turn
TRAIL = 0.35
DIM = 0.03


class FanRelay(CorsairEffect, GradientEffect):
    NAME = "Fan Relay"
    # Effect declares HIDDEN_KEYS = None, so every list override trips bad-override.
    HIDDEN_KEYS: ClassVar[list[str]] = ["gradient_roll"]  # pyrefly: ignore[bad-override]

    class Config(GradientEffect.Config):
        laps_per_beat: CoercedFloat = Field(
            0.5, description="Laps of a fan the runner makes per beat", ge=0.1, le=2.0
        )

    config = TypedConfig(Config)

    def on_activate(self, pixel_count: int) -> None:
        self._fans = fan_layout(pixel_count)
        self._track = 0.0

    @override
    def render(self) -> None:
        self._track += (
            self.song_moved() * self.config.laps_per_beat + self.step() * 0.05
        )
        fans = self._fans
        count = fans.count
        # A lap of each fan in turn, from the top one down, then back to the top
        track = self._track % count
        runner = int(track)
        at = track % 1
        behind = (at - fans.angle) % 1
        trail = np.where(behind < TRAIL, (1 - behind / TRAIL) ** 2, 0.0)
        running = fans.fan == runner
        # The fan just handed over still glows, fading as the lap goes on
        handed = fans.fan == (runner - 1) % count
        rim = np.where(
            running, trail, np.where(handed & (count > 1), 0.3 * (1 - at), 0.0)
        )
        hub = np.where(running, 0.3, 0.0)
        level = np.where(
            fans.ring == FAN_RIM, rim, np.where(fans.ring == FAN_HUB, hub, 0.0)
        )
        colors = self.get_gradient_color_vectorized1d(
            np.full(level.size, track / count * 0.999)
        )
        self.pixels = colors * np.maximum(level, DIM)[:, None]
