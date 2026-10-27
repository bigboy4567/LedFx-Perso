from unittest.mock import MagicMock

from ledfx.api.schema import HIDDEN_EFFECTS
from ledfx.effects import Effect
from ledfx.utils import RegistryLoader


def test_hidden_effects_are_all_registered() -> None:
    # A typo would leave the effect in the picker, silently
    registered = RegistryLoader(MagicMock(), Effect, "ledfx.effects").classes()
    assert HIDDEN_EFFECTS <= registered.keys()
