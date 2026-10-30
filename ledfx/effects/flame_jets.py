from typing import Literal

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
    frame_step,
    heat_colors,
)

# A jet roars up quickly, burns, and dies down
LIFE = 0.9
RISE = 0.12
# In a sweep, each jet fires this long after the one before
SWEEP_GAP = 0.06
COLD = np.array((150.0, 210.0, 255.0))

Style = Literal["Fire", "CO2"]
Pattern = Literal["All", "Alternate", "Random", "Sweep"]


class FlameJets(AudioReactiveEffect):
    NAME = "Flame Jets"
    CATEGORY = CUSTOM_CATEGORY

    class Config(AudioReactiveEffect.Config):
        jets: CoercedInt = Field(4, description="Jets along the strip", ge=1, le=12)
        size: CoercedFloat = Field(
            0.15,
            description="Width of a jet's blast, as a share of the strip",
            ge=0.03,
            le=0.5,
        )
        style: Style = Field("Fire", description="Flame jets, or cold CO2 blasts")
        pattern: Pattern = Field(
            "All", description="Which jets fire on a hit, and in what order"
        )
        trigger: Trigger = Field(
            "Beat", description="Fire on the bass or on every percussive hit"
        )

    config = TypedConfig(Config)

    def on_activate(self, pixel_count: int) -> None:
        self._x: FloatArray = np.arange(pixel_count, dtype=float)
        self._shots = 0
        self._place(pixel_count)
        self._latch = BeatLatch()

    def _place(self, pixel_count: int) -> None:
        count = self.config.jets
        self._at: FloatArray = (np.arange(count) + 0.5) / count * pixel_count - 0.5
        self._ages: FloatArray = np.full(count, np.inf)

    @override
    def config_updated(self, config: object) -> None:
        if not hasattr(self, "_rng"):
            self._rng = np.random.default_rng()
        pixels = getattr(self, "pixels", None)
        if (
            pixels is not None
            and hasattr(self, "_ages")
            and self._ages.size != self.config.jets
        ):
            self._place(len(pixels))

    @override
    def audio_data_updated(self, data: AudioAnalysisSource) -> None:
        self._latch.listen(data, self.config.trigger)

    def _fire(self) -> None:
        count = self._ages.size
        index = np.arange(count)
        match self.config.pattern:
            case "All":
                self._ages[:] = 0.0
            case "Alternate":
                self._ages[index % 2 == self._shots % 2] = 0.0
            case "Random":
                chosen = self._rng.random(count) < 0.5
                chosen[self._rng.integers(count)] = True
                self._ages[chosen] = 0.0
            case "Sweep":
                # A wave of fire along the row: later jets wait their turn
                self._ages[:] = -index * SWEEP_GAP
        self._shots += 1

    @override
    def render(self) -> None:
        self._ages += frame_step(self.passed)
        if self._latch.take(self.now):
            self._fire()

        n = self.pixel_count
        heat = np.zeros(n)
        reach = max(0.6, self.config.size * n / 2)
        for at, age in zip(self._at, self._ages, strict=True):
            if not 0 <= age < LIFE:
                continue
            grown = min(1.0, age / RISE)
            dying = 1 - (age / LIFE) ** 2
            half = reach * grown * (1 - max(0.0, (age - 0.6) / 0.3) * 0.7)
            lo, hi = max(0, int(at - half) - 1), min(n, int(at + half) + 2)
            core = np.clip(1 - np.abs(self._x[lo:hi] - at) / max(half, 0.5), 0, 1)
            # The fire churns: every pixel of the column flickers on its own
            churn = 0.7 + 0.3 * self._rng.random(hi - lo)
            np.maximum(heat[lo:hi], core * dying * churn, out=heat[lo:hi])
        if self.config.style == "Fire":
            self.pixels = heat_colors(heat)
        else:
            self.pixels = np.clip(COLD * heat[:, None] * 1.3, 0, 255)
