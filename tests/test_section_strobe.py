"""Section Strobe: whole sections flash on the beat, in the configured pattern."""

from typing import cast
from unittest.mock import MagicMock

import numpy as np
import pytest

from ledfx.effects.audio import AudioAnalysisSource
from ledfx.effects.section_strobe import SectionStrobe
from ledfx.effects.utils.custom import TRIGGER_COOLDOWN


class FakeAudio:
    def __init__(self, beat: bool = False, onset: bool = False) -> None:
        self.beat = beat
        self.hit = onset

    def volume_beat_now(self) -> bool:
        return self.beat

    def onset(self) -> bool:
        return self.hit


def make_effect(count: int, **config: object) -> SectionStrobe:
    effect = SectionStrobe(
        MagicMock(), SectionStrobe.config_model().model_validate(config)
    )
    effect.pixels = np.zeros((count, 3))
    SectionStrobe.on_activate(effect, count)
    return effect


def beat(effect: SectionStrobe, beat: bool = True, onset: bool = False) -> None:
    effect.audio_data_updated(cast(AudioAnalysisSource, FakeAudio(beat, onset)))
    # Well past the cooldown, and long enough for the previous flash to fade out
    effect.now += 1.0
    effect.passed = 1.0
    effect.render()


def lit_sections(effect: SectionStrobe) -> list[int]:
    return [int(i) for i in np.flatnonzero(effect._levels > 0.99)]


@pytest.mark.parametrize("count", [1, 2, 7, 16, 150, 37555])
def test_renders_valid_frames_on_any_length(count: int) -> None:
    for pattern in ("Random", "Chase", "Bounce", "Alternate"):
        effect = make_effect(count, pattern=pattern, sections=8, sections_per_beat=3)
        for frame in range(20):
            beat(effect, beat=frame % 2 == 0)
            pixels = effect.pixels
            assert pixels is not None
            assert pixels.shape == (count, 3)
            assert np.isfinite(pixels).all()
            assert pixels.min() >= 0
            assert pixels.max() <= 255


def test_a_beat_flashes_whole_sections_only() -> None:
    effect = make_effect(80, sections=8, sections_per_beat=2)
    beat(effect)
    assert effect.pixels is not None
    lit = effect.pixels[:, 0] > 0
    # 8 sections of 10 pixels: exactly two of them, fully lit
    assert lit.sum() == 20
    for start in range(0, 80, 10):
        assert lit[start : start + 10].all() or not lit[start : start + 10].any()


def test_silence_stays_dark_and_flashes_fade() -> None:
    effect = make_effect(80)
    beat(effect, beat=False)
    assert effect.pixels is not None
    assert effect.pixels.max() == 0
    beat(effect)
    assert effect.pixels.max() == 255
    # A second of 60 fps frames at the default decay leaves nothing visible
    for _ in range(60):
        effect.now += 1 / 60
        effect.passed = 1 / 60
        effect.render()
    assert effect.pixels.max() < 1


def test_chase_marches_forward_and_wraps() -> None:
    effect = make_effect(80, pattern="Chase", sections=4, sections_per_beat=1)
    order = []
    for _ in range(6):
        beat(effect)
        order.append(lit_sections(effect))
    assert order == [[0], [1], [2], [3], [0], [1]]


def test_bounce_turns_around_at_the_ends() -> None:
    effect = make_effect(80, pattern="Bounce", sections=4, sections_per_beat=1)
    order = []
    for _ in range(8):
        beat(effect)
        order.append(lit_sections(effect)[0])
    assert order == [0, 1, 2, 3, 2, 1, 0, 1]


def test_alternate_switches_odd_and_even() -> None:
    effect = make_effect(80, pattern="Alternate", sections=6)
    beat(effect)
    first = lit_sections(effect)
    beat(effect)
    second = lit_sections(effect)
    assert sorted(first + second) == list(range(6))
    assert {len(first), len(second)} == {3}


def test_random_never_repeats_a_section_back_to_back() -> None:
    effect = make_effect(80, pattern="Random", sections=8, sections_per_beat=2)
    previous: set[int] = set()
    for _ in range(200):
        beat(effect)
        current = set(lit_sections(effect))
        assert len(current) == 2
        assert not current & previous
        previous = current


def test_trigger_choice_and_cooldown() -> None:
    effect = make_effect(80, trigger="Percussion")
    beat(effect, beat=True, onset=False)
    assert not lit_sections(effect)
    beat(effect, beat=False, onset=True)
    first = effect._latch.last
    # A second hit inside the cooldown is the same drum hit detected twice
    effect.audio_data_updated(cast(AudioAnalysisSource, FakeAudio(onset=True)))
    effect.now += TRIGGER_COOLDOWN / 2
    effect.passed = TRIGGER_COOLDOWN / 2
    effect.render()
    assert effect._latch.last == first


def test_gradient_colors_each_section() -> None:
    effect = make_effect(80, sections=8, sections_per_beat=8, use_gradient=True)
    beat(effect)
    assert effect.pixels is not None
    # The default gradient starts red and ends pink: the two ends differ
    assert not np.array_equal(effect.pixels[0], effect.pixels[-1])


def test_changing_sections_rebuilds_but_colors_keep_the_pattern() -> None:
    effect = make_effect(80, pattern="Chase", sections=4)
    beat(effect)
    beat(effect)
    effect.update_config({"strobe_color": "#FF0000"})
    assert effect._cursor == 2
    effect.update_config({"sections": 10})
    assert effect._levels.size == 10
    assert effect._cursor == 0
