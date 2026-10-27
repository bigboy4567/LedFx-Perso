"""Paint on a strip with a phone: the /phone page streams where the phone points."""

from collections import deque
from dataclasses import dataclass

import numpy as np
from pydantic import Field
from typing_extensions import override

from ledfx.configuration.fields import CoercedFloat
from ledfx.configuration.plugin import TypedConfig
from ledfx.effects import Effect
from ledfx.effects.utils.custom import CUSTOM_CATEGORY, FloatArray, frame_step

# A phone that stops reporting (screen locked, page closed) loses its cursor
CURSOR_TIMEOUT = 2.0
# Calibration marker blink rate, in flashes per second
MARK_BLINK = 3.0
# Commands waiting for the next frame; a stalled render drops the oldest
INBOX_SIZE = 1024
WHITE: FloatArray = np.full(3, 255.0)


@dataclass(frozen=True)
class Stroke:
    """Where one phone points. x is 0 to 1 along the strip, None when off it."""

    client: str
    x: float | None
    down: bool
    color: FloatArray
    size: float
    erase: bool


@dataclass(frozen=True)
class Clear:
    pass


@dataclass(frozen=True)
class Fill:
    color: FloatArray


@dataclass(frozen=True)
class Mark:
    """Blink a spot for the phone to aim at while it calibrates; None stops it."""

    x: float | None


Command = Stroke | Clear | Fill | Mark


@dataclass
class Cursor:
    x: float | None
    down: bool
    color: FloatArray
    radius: float
    erase: bool
    seen: float


class PhonePaint(Effect):
    NAME = "Phone Paint"
    CATEGORY = CUSTOM_CATEGORY

    class Config(Effect.Config):
        fade: CoercedFloat = Field(
            0.0,
            description="Seconds for paint to fade away; 0 keeps it until cleared",
            ge=0.0,
            le=30.0,
        )
        softness: CoercedFloat = Field(
            0.5, description="How soft the edge of the brush is", ge=0.0, le=1.0
        )
        cursor: bool = Field(True, description="Show where each phone points")
        cursor_brightness: CoercedFloat = Field(
            0.5, description="Brightness of the cursor", ge=0.05, le=1.0
        )
        screen_colors: bool = Field(
            True,
            description="Match the phone's colors: LEDs show a screen's faint tints too brightly, so a red would turn pink",
        )

    config = TypedConfig(Config)

    def __init__(self, ledfx: object, config: object) -> None:
        # The web server thread fills this while the render thread drains it:
        # deque appends and pops are atomic, so neither needs the effect lock
        self._inbox: deque[Command] = deque(maxlen=INBOX_SIZE)
        super().__init__(ledfx, config)

    def on_activate(self, pixel_count: int) -> None:
        self._canvas: FloatArray = np.zeros((pixel_count, 3))
        self._index: FloatArray = np.arange(pixel_count, dtype=float)
        self._cursors: dict[str, Cursor] = {}
        self._mark: float | None = None
        self._clock = 0.0

    def send(self, command: Command) -> None:
        self._inbox.append(command)

    def _position(self, x: float) -> float:
        return x * (len(self._canvas) - 1)

    def _radius(self, size: float) -> float:
        # size is the brush width as a share of the strip; never under one pixel
        return max(0.5, size * len(self._canvas) / 2)

    def _paint(self, start: float, end: float, cursor: Cursor) -> None:
        """Brush every pixel near the segment between two positions."""
        low, high = min(start, end), max(start, end)
        radius = cursor.radius
        first = max(0, int(np.floor(low - radius)))
        last = min(len(self._canvas), int(np.ceil(high + radius)) + 1)
        if first >= last:
            return
        index = self._index[first:last]
        distance = np.maximum(0.0, np.maximum(low - index, index - high))
        edge = radius * self.config.softness + 1e-6
        alpha = np.clip((radius - distance) / edge, 0.0, 1.0)[:, None]
        color = np.zeros(3) if cursor.erase else cursor.color
        region = self._canvas[first:last]
        region += (color - region) * alpha

    def _led(self, color: FloatArray) -> FloatArray:
        """A color picked on a screen, as the LED drive that looks like it."""
        if not self.config.screen_colors:
            return color
        # Screens encode brightness with the sRGB curve; LEDs light in proportion
        # to the value they get, so decode it: (255, 42, 42) is red, not pink
        level = np.clip(color / 255, 0.0, 1.0)
        linear = np.where(
            level <= 0.04045, level / 12.92, ((level + 0.055) / 1.055) ** 2.4
        )
        return linear * 255

    def _apply(self, command: Command) -> None:
        if isinstance(command, Clear):
            self._canvas[:] = 0
        elif isinstance(command, Fill):
            self._canvas[:] = self._led(command.color)
        elif isinstance(command, Mark):
            self._mark = command.x
        else:
            self._stroke(command)

    def _stroke(self, stroke: Stroke) -> None:
        previous = self._cursors.get(stroke.client)
        cursor = Cursor(
            x=stroke.x,
            down=stroke.down,
            color=self._led(stroke.color),
            radius=self._radius(stroke.size),
            erase=stroke.erase,
            seen=self._clock,
        )
        self._cursors[stroke.client] = cursor
        if stroke.x is None or not stroke.down:
            return
        here = start = self._position(stroke.x)
        # Join to the last point so a fast sweep leaves a line, not dots
        if previous is not None and previous.down and previous.x is not None:
            start = self._position(previous.x)
        self._paint(start, here, cursor)

    def _glow(
        self, frame: FloatArray, x: float, radius: float, color: FloatArray
    ) -> None:
        center = self._position(x)
        first = max(0, int(center - radius - 1))
        last = min(len(frame), int(center + radius) + 2)
        if first >= last:
            return
        distance = np.abs(self._index[first:last] - center)
        level = np.clip(1.0 - distance / (radius + 0.5), 0.0, 1.0)[:, None]
        np.maximum(frame[first:last], color * level, out=frame[first:last])

    @override
    def render(self) -> None:
        dt = frame_step(self.passed)
        self._clock += dt
        if self.config.fade > 0:
            self._canvas *= float(np.exp(-dt / self.config.fade))
        while self._inbox:
            self._apply(self._inbox.popleft())

        frame = self._canvas.copy()
        stale = [
            client
            for client, cursor in self._cursors.items()
            if self._clock - cursor.seen > CURSOR_TIMEOUT
        ]
        for client in stale:
            del self._cursors[client]
        if self.config.cursor:
            for cursor in self._cursors.values():
                # Paint shows itself; the cursor marks where a brush is aimed
                # and, for the eraser, what it is about to wipe
                if cursor.x is None or (cursor.down and not cursor.erase):
                    continue
                color = WHITE if cursor.erase else cursor.color
                self._glow(
                    frame,
                    cursor.x,
                    cursor.radius,
                    color * self.config.cursor_brightness,
                )
        if self._mark is not None and int(self._clock * MARK_BLINK * 2) % 2 == 0:
            width = max(1.0, len(frame) / 100)
            self._glow(frame, self._mark, width, WHITE)
        self.pixels = np.clip(frame, 0, 255)
