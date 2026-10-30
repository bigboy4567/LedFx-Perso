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
    Trigger,
    color_array,
    frame_step,
    hue_colors,
    paint_glow,
)

CORE = color_array("#FFFFFF")
HALO = color_array("#FFB060")
STREAK = color_array("#2050FF")
# Ghosts sit on the line through the middle of the lens, at these multiples of the
# light's distance from it; negative ones fall on the other side
GHOSTS = (-0.6, -0.3, 0.45, -1.0, 0.8, 1.3)
GHOST_SIZES = (0.025, 0.012, 0.018, 0.04, 0.01, 0.03)


class LensFlare(AudioReactiveEffect):
    NAME = "Lens Flare"
    CATEGORY = CUSTOM_CATEGORY

    class Config(AudioReactiveEffect.Config):
        ghosts: CoercedInt = Field(
            4, description="Colored ghost reflections trailing the light", ge=0, le=6
        )
        sweep_time: CoercedFloat = Field(
            1.2, description="Seconds the light takes to sweep across", ge=0.3, le=4.0
        )
        trigger: Trigger = Field(
            "Beat", description="Sweep a flare on the bass or on every percussive hit"
        )

    config = TypedConfig(Config)

    def on_activate(self, pixel_count: int) -> None:
        self._x: FloatArray = np.arange(pixel_count, dtype=float)
        self._age = np.inf
        self._heading = 1.0
        self._latch = BeatLatch()

    @override
    def config_updated(self, config: object) -> None:
        if not hasattr(self, "_rng"):
            self._rng = np.random.default_rng()

    @override
    def audio_data_updated(self, data: AudioAnalysisSource) -> None:
        self._latch.listen(data, self.config.trigger)

    def light_at(self) -> float | None:
        """Where the light is, as a share of the strip, or None between flares."""
        progress = self._age / self.config.sweep_time
        if progress >= 1:
            return None
        along = -0.1 + 1.2 * progress
        return along if self._heading > 0 else 1 - along

    @override
    def render(self) -> None:
        self._age += frame_step(self.passed)
        if self._latch.take(self.now) and self.light_at() is None:
            self._age = 0.0
            self._heading = 1.0 if self._rng.random() < 0.5 else -1.0

        n = self.pixel_count
        pixels = np.zeros((n, 3))
        light = self.light_at()
        if light is None:
            self.pixels = pixels
            return
        strength = float(np.sin(np.pi * self._age / self.config.sweep_time))
        # The anamorphic streak tints the whole picture as the light crosses
        pixels += STREAK * 0.12 * strength
        span = max(n - 1, 1)
        paint_glow(
            pixels, self._x, light * span, max(2.0, 0.15 * n), HALO, 0.35 * strength
        )
        for index in range(self.config.ghosts):
            ghost = 0.5 + (light - 0.5) * GHOSTS[index]
            tint = hue_colors(np.array((0.55 + index * 0.17,)))[0]
            tint = tint + (255 - tint) * 0.3
            size = max(0.7, GHOST_SIZES[index] * n)
            paint_glow(pixels, self._x, ghost * span, size, tint, 0.3 * strength)
        paint_glow(pixels, self._x, light * span, max(0.8, 0.015 * n), CORE, strength)
        self.pixels = np.clip(pixels, 0, 255)
