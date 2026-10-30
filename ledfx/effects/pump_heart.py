import numpy as np
from pydantic import Field
from typing_extensions import override

from ledfx.configuration.fields import Color
from ledfx.configuration.plugin import TypedConfig
from ledfx.effects.utils.corsair import CorsairEffect, aio_layout
from ledfx.effects.utils.custom import color_array

# The second beat of a heartbeat comes this long after the first, a little weaker
DUB_DELAY = 0.18
DUB_STRENGTH = 0.6
# The radiator fans echo the pump this long later, as blood reaching the limbs
ECHO = 0.12
DECAY = 7.0
RESTING = 0.06


class PumpHeart(CorsairEffect):
    NAME = "Pump Heart"

    class Config(CorsairEffect.Config):
        color: Color = Field("#FF0028", description="Color of the heartbeat")

    config = TypedConfig(Config)

    def on_activate(self, pixel_count: int) -> None:
        self._aio = aio_layout(pixel_count)
        self._since = np.inf

    @override
    def config_updated(self, config: object) -> None:
        self._color = color_array(self.config.color)

    def pulse(self, since: float) -> float:
        """How bright a lub-dub is this long after the beat."""
        lub = np.exp(-since * DECAY) if since >= 0 else 0.0
        dub = (
            DUB_STRENGTH * np.exp(-(since - DUB_DELAY) * DECAY)
            if since >= DUB_DELAY
            else 0.0
        )
        return float(max(lub, dub))

    @override
    def render(self) -> None:
        self._since += self.step()
        if self.beat():
            self._since = 0.0
        pump = max(RESTING, self.pulse(self._since))
        fans = max(RESTING, self.pulse(self._since - ECHO) * 0.8)
        level = np.where(self._aio.pump, pump, fans)
        self.pixels = self._color * level[:, None]
