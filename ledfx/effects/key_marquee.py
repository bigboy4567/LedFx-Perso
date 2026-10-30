import numpy as np
from pydantic import Field
from typing_extensions import override

from ledfx.configuration.fields import CoercedFloat, Color
from ledfx.configuration.plugin import TypedConfig
from ledfx.effects.utils.corsair import CorsairEffect, keyboard_layout, keyboard_rows
from ledfx.effects.utils.custom import BoolArray, IntArray, color_array

# A tiny font, three columns wide and five rows tall
FONT = {
    "A": (".#.", "#.#", "###", "#.#", "#.#"),
    "B": ("##.", "#.#", "##.", "#.#", "##."),
    "C": (".##", "#..", "#..", "#..", ".##"),
    "D": ("##.", "#.#", "#.#", "#.#", "##."),
    "E": ("###", "#..", "##.", "#..", "###"),
    "F": ("###", "#..", "##.", "#..", "#.."),
    "G": (".##", "#..", "#.#", "#.#", ".##"),
    "H": ("#.#", "#.#", "###", "#.#", "#.#"),
    "I": ("###", ".#.", ".#.", ".#.", "###"),
    "J": ("..#", "..#", "..#", "#.#", ".#."),
    "K": ("#.#", "#.#", "##.", "#.#", "#.#"),
    "L": ("#..", "#..", "#..", "#..", "###"),
    "M": ("#.#", "###", "###", "#.#", "#.#"),
    "N": ("##.", "#.#", "#.#", "#.#", "#.#"),
    "O": (".#.", "#.#", "#.#", "#.#", ".#."),
    "P": ("##.", "#.#", "##.", "#..", "#.."),
    "Q": (".#.", "#.#", "#.#", "##.", ".##"),
    "R": ("##.", "#.#", "##.", "#.#", "#.#"),
    "S": (".##", "#..", ".#.", "..#", "##."),
    "T": ("###", ".#.", ".#.", ".#.", ".#."),
    "U": ("#.#", "#.#", "#.#", "#.#", "###"),
    "V": ("#.#", "#.#", "#.#", "#.#", ".#."),
    "W": ("#.#", "#.#", "###", "###", "#.#"),
    "X": ("#.#", "#.#", ".#.", "#.#", "#.#"),
    "Y": ("#.#", "#.#", ".#.", ".#.", ".#."),
    "Z": ("###", "..#", ".#.", "#..", "###"),
    "0": ("###", "#.#", "#.#", "#.#", "###"),
    "1": (".#.", "##.", ".#.", ".#.", "###"),
    "2": ("##.", "..#", ".#.", "#..", "###"),
    "3": ("##.", "..#", ".#.", "..#", "##."),
    "4": ("#.#", "#.#", "###", "..#", "..#"),
    "5": ("###", "#..", "##.", "..#", "##."),
    "6": (".##", "#..", "###", "#.#", "###"),
    "7": ("###", "..#", ".#.", ".#.", ".#."),
    "8": ("###", "#.#", "###", "#.#", "###"),
    "9": ("###", "#.#", "###", "..#", "##."),
    " ": ("...", "...", "...", "...", "..."),
    "!": (".#.", ".#.", ".#.", "...", ".#."),
    "?": ("##.", "..#", ".#.", "...", ".#."),
    "-": ("...", "...", "###", "...", "..."),
    ".": ("...", "...", "...", "...", ".#."),
    ":": ("...", ".#.", "...", ".#.", "..."),
}
GLYPH_ROWS = 5
# Key columns across the board, and blank columns between the end of the text and its start
COLUMNS = 24
GAP = 6
# The text sits on the five rows from the F keys to the bottom letter row
FIRST_ROW = 2
FLASH = 5.0


def text_bitmap(text: str) -> BoolArray:
    """The text in the tiny font, a column of blank between letters: rows by columns."""
    columns: list[list[bool]] = []
    for letter in text.upper():
        glyph = FONT.get(letter, FONT[" "])
        for column in range(3):
            columns.append([glyph[row][column] == "#" for row in range(GLYPH_ROWS)])
        columns.append([False] * GLYPH_ROWS)
    columns += [[False] * GLYPH_ROWS] * GAP
    return np.array(columns, dtype=bool).T


class KeyMarquee(CorsairEffect):
    NAME = "Key Marquee"

    class Config(CorsairEffect.Config):
        text: str = Field(
            "LEDFX", description="Text to scroll across the keys", max_length=60
        )
        color: Color = Field("#FF8000", description="Color of the text")
        speed: CoercedFloat = Field(
            8.0, description="Key columns the text scrolls a second", ge=1.0, le=30.0
        )

    config = TypedConfig(Config)

    def on_activate(self, pixel_count: int) -> None:
        board = keyboard_layout(pixel_count)
        rows, count = keyboard_rows(board)
        # On the real board the letters sit on the key rows; on any other strip, their middle line
        glyph_row = (
            rows - FIRST_ROW
            if count >= FIRST_ROW + GLYPH_ROWS
            else np.full(rows.size, 2)
        )
        self._glyph_row: IntArray = glyph_row
        self._column: IntArray = np.round(board.x * (COLUMNS - 1)).astype(int)
        self.scrolled = 0.0
        self._flash = 0.0

    @override
    def config_updated(self, config: object) -> None:
        self._color = color_array(self.config.color)
        self._bitmap = text_bitmap(self.config.text)

    @override
    def render(self) -> None:
        dt = self.step()
        self.scrolled += dt * self.config.speed * (0.6 + 0.8 * self.loudness)
        self._flash *= float(np.exp(-dt * FLASH))
        if self.beat():
            self._flash = 1.0
        bitmap = self._bitmap
        # The text slides in from the right and out to the left, round and round
        column = (self._column + int(self.scrolled)) % bitmap.shape[1]
        row = self._glyph_row
        on_text = (row >= 0) & (row < GLYPH_ROWS)
        lit = on_text & bitmap[np.clip(row, 0, GLYPH_ROWS - 1), column]
        level = np.where(lit, 0.7 + 0.3 * self._flash, 0.02)
        self.pixels = self._color * level[:, None]
