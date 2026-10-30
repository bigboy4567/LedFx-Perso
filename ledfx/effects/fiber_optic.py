import numpy as np
from pydantic import Field
from typing_extensions import override

from ledfx.configuration.fields import CoercedFloat, CoercedInt
from ledfx.configuration.plugin import TypedConfig
from ledfx.effects.audio import AudioAnalysisSource, AudioReactiveEffect
from ledfx.effects.utils.custom import (
    CUSTOM_CATEGORY,
    FloatArray,
    color_array,
    frame_step,
    paint_glow,
)

# The color wheel turning under the fibres: four filters, as in the old lamps
WHEEL = np.array([color_array(c) for c in ("#FF1020", "#20FF40", "#2040FF", "#FFD000")])
# Share of each filter that blurs into the next as it passes under a fibre
BLEND = 0.25


class FiberOptic(AudioReactiveEffect):
    NAME = "Fiber Optic"
    CATEGORY = CUSTOM_CATEGORY

    class Config(AudioReactiveEffect.Config):
        fibers: CoercedInt = Field(
            60, description="Fibre tips along the strip", ge=5, le=300
        )
        wheel_speed: CoercedFloat = Field(
            0.3, description="Turns of the color wheel per second", ge=0.0, le=3.0
        )
        sparkle: CoercedFloat = Field(
            0.5,
            description="How much the treble makes the tips sparkle",
            ge=0.0,
            le=1.0,
        )

    config = TypedConfig(Config)

    def on_activate(self, pixel_count: int) -> None:
        self._x: FloatArray = np.arange(pixel_count, dtype=float)
        self._spread()
        self._turn = 0.0
        self._mids = 0.0
        self._highs = 0.0

    def _spread(self) -> None:
        count = self.config.fibers
        self._at: FloatArray = self._rng.random(count)
        # Where on the wheel each fibre picks up its light
        self._seat: FloatArray = self._rng.random(count)

    @override
    def config_updated(self, config: object) -> None:
        if not hasattr(self, "_rng"):
            self._rng = np.random.default_rng()
        if hasattr(self, "_at") and self._at.size != self.config.fibers:
            self._spread()

    @override
    def audio_data_updated(self, data: AudioAnalysisSource) -> None:
        self._mids = float(data.mids_power())
        self._highs = float(data.high_power())

    def colors(self) -> FloatArray:
        """The color each fibre carries from the wheel right now."""
        place = (self._seat + self._turn) % 1 * len(WHEEL)
        filter_index = place.astype(int) % len(WHEEL)
        within = place - np.floor(place)
        blend = np.clip((within - (1 - BLEND)) / BLEND, 0, 1)[:, None]
        following = WHEEL[(filter_index + 1) % len(WHEEL)]
        return WHEEL[filter_index] * (1 - blend) + following * blend

    @override
    def render(self) -> None:
        self._turn = (
            self._turn + frame_step(self.passed) * self.config.wheel_speed
        ) % 1
        n = self.pixel_count
        count = self._at.size
        twinkle = 1 - self.config.sparkle * self._highs * self._rng.random(count)
        levels = (0.45 + 0.55 * min(1.0, self._mids * 1.5)) * twinkle
        pixels = np.zeros((n, 3))
        size = max(0.5, n / 400)
        for at, color, level in zip(self._at, self.colors(), levels, strict=True):
            paint_glow(pixels, self._x, float(at) * (n - 1), size, color, float(level))
        self.pixels = np.clip(pixels, 0, 255)
