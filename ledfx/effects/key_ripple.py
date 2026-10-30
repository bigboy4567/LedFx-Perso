from typing import ClassVar, Literal

import numpy as np
from pydantic import Field
from typing_extensions import override

from ledfx.configuration.fields import CoercedFloat
from ledfx.configuration.plugin import TypedConfig
from ledfx.effects.audio import AudioAnalysisSource, AudioReactiveEffect
from ledfx.effects.gradient import GradientEffect
from ledfx.effects.utils.corsair import (
    CORSAIR_CATEGORY,
    KEYBOARD_DEPTH,
    LOGO,
    keyboard_layout,
)
from ledfx.effects.utils.custom import (
    BeatLatch,
    FloatArray,
    Trigger,
    frame_step,
)

# Ripples spreading at once, at most; the oldest makes room
MAX_RIPPLES = 8
# A ripple fades out by the time it has spread this far, in keyboard widths
REACH = 1.2
WHITE = np.array((255.0, 255.0, 255.0))

Origin = Literal["Random key", "Middle", "Light bar"]


class KeyRipple(AudioReactiveEffect, GradientEffect):
    NAME = "Key Ripple"
    CATEGORY = CORSAIR_CATEGORY
    # Effect declares HIDDEN_KEYS = None, so every list override trips bad-override.
    HIDDEN_KEYS: ClassVar[list[str]] = ["gradient_roll"]  # pyrefly: ignore[bad-override]

    class Config(GradientEffect.Config):
        origin: Origin = Field(
            "Random key", description="Where the ripples start on the keyboard"
        )
        speed: CoercedFloat = Field(
            1.2,
            description="How fast a ripple spreads, in keyboard widths per second",
            ge=0.2,
            le=4.0,
        )
        width: CoercedFloat = Field(
            0.06,
            description="Width of a ripple's ring, in keyboard widths",
            ge=0.02,
            le=0.3,
        )
        trigger: Trigger = Field(
            "Percussion",
            description="Start a ripple on the bass or on every percussive hit",
        )

    config = TypedConfig(Config)

    def on_activate(self, pixel_count: int) -> None:
        board = keyboard_layout(pixel_count)
        self._x: FloatArray = board.x
        # Distances are measured in keyboard widths, so the board is shallow
        self._y: FloatArray = board.y * KEYBOARD_DEPTH
        self._logo = board.zone == LOGO
        self._centers: FloatArray = np.zeros((MAX_RIPPLES, 2))
        self._ages: FloatArray = np.full(MAX_RIPPLES, np.inf)
        self._hues: FloatArray = np.zeros(MAX_RIPPLES)
        self._flash = 0.0
        self._latch = BeatLatch()

    @override
    def config_updated(self, config: object) -> None:
        if not hasattr(self, "_rng"):
            self._rng = np.random.default_rng()

    @override
    def audio_data_updated(self, data: AudioAnalysisSource) -> None:
        self._latch.listen(data, self.config.trigger)

    def _start(self) -> None:
        slot = int(np.argmax(self._ages))
        match self.config.origin:
            case "Random key":
                key = int(self._rng.integers(self._x.size))
                center = (self._x[key], self._y[key])
            case "Middle":
                center = (0.5, 0.5 * KEYBOARD_DEPTH)
            case "Light bar":
                center = (float(self._rng.random()), 0.0)
        self._centers[slot] = center
        self._ages[slot] = 0.0
        self._hues[slot] = self._rng.random()
        self._flash = 1.0

    @override
    def render(self) -> None:
        dt = frame_step(self.passed)
        self._ages += dt
        self._flash *= float(np.exp(-dt * 6))
        if self._latch.take(self.now):
            self._start()

        pixels = np.zeros((self._x.size, 3))
        colors = self.get_gradient_color_vectorized1d(self._hues)
        for (cx, cy), age, color in zip(self._centers, self._ages, colors, strict=True):
            radius = age * self.config.speed
            if radius > REACH:
                continue
            distance = np.hypot(self._x - cx, self._y - cy)
            ring = np.exp(-(((distance - radius) / self.config.width) ** 2))
            np.maximum(
                pixels, color * (ring * (1 - radius / REACH))[:, None], out=pixels
            )
        # The logo flashes with every new ripple
        pixels[self._logo] = WHITE * max(0.1, self._flash)
        self.pixels = np.clip(pixels, 0, 255)
