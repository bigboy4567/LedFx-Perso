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
    IntArray,
    Trigger,
    color_array,
    frame_step,
    paint_glow,
)

# The ultraviolet tube itself shows as a deep violet
UV = color_array("#1C0040")
# Fluorescent paints glowing under it
NEONS = np.array(
    [
        color_array(c)
        for c in ("#39FF14", "#FF10F0", "#DFFF00", "#FF5F1F", "#00FFFF", "#FF3131")
    ]
)
# Share of the spots that flash on a hit, and the chance one is repainted elsewhere
FLASH_SHARE = 0.3
REPAINT = 0.15


class Blacklight(AudioReactiveEffect):
    NAME = "Blacklight"
    CATEGORY = CUSTOM_CATEGORY

    class Config(AudioReactiveEffect.Config):
        spots: CoercedInt = Field(12, description="Fluorescent spots", ge=2, le=60)
        spot_size: CoercedFloat = Field(
            0.02,
            description="Size of a spot, as a share of the strip",
            ge=0.003,
            le=0.1,
        )
        glow: CoercedFloat = Field(
            0.5, description="How much the mids make the paint glow", ge=0.0, le=1.0
        )
        trigger: Trigger = Field(
            "Beat", description="Flash spots on the bass or on every percussive hit"
        )

    config = TypedConfig(Config)

    def on_activate(self, pixel_count: int) -> None:
        self._x: FloatArray = np.arange(pixel_count, dtype=float)
        self._paint()
        self._mids = 0.0
        self._latch = BeatLatch()

    def _paint(self) -> None:
        count = self.config.spots
        self._at: FloatArray = self._rng.random(count)
        self._paints: IntArray = self._rng.integers(0, len(NEONS), count)
        self._phase: FloatArray = self._rng.uniform(0, 2 * np.pi, count)
        self._flash: FloatArray = np.zeros(count)

    @override
    def config_updated(self, config: object) -> None:
        if not hasattr(self, "_rng"):
            self._rng = np.random.default_rng()
        if hasattr(self, "_at") and self._at.size != self.config.spots:
            self._paint()

    @override
    def audio_data_updated(self, data: AudioAnalysisSource) -> None:
        self._mids = float(data.mids_power())
        self._latch.listen(data, self.config.trigger)

    @override
    def render(self) -> None:
        dt = frame_step(self.passed)
        count = self._at.size
        self._phase += dt * 1.5
        self._flash *= float(np.exp(-dt * 5))
        if self._latch.take(self.now):
            self._flash[self._rng.random(count) < FLASH_SHARE] = 1.0
            if self._rng.random() < REPAINT:
                spot = int(self._rng.integers(count))
                self._at[spot] = self._rng.random()
                self._paints[spot] = self._rng.integers(len(NEONS))

        n = self.pixel_count
        pixels = np.tile(UV * (0.6 + 0.4 * self._mids), (n, 1))
        radius = max(0.6, self.config.spot_size * n)
        glow = 0.35 + self.config.glow * self._mids * (0.5 + 0.5 * np.sin(self._phase))
        for at, paint, amount in zip(
            self._at, self._paints, np.minimum(glow + self._flash, 1.3), strict=True
        ):
            paint_glow(
                pixels,
                self._x,
                float(at) * (n - 1),
                radius,
                NEONS[paint],
                float(amount),
            )
        self.pixels = np.clip(pixels, 0, 255)
