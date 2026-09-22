import pytest

from config import load_preferences
from helpers import TODAY, TZ
from models import Window


@pytest.fixture
def window() -> Window:
    return Window(TODAY, TZ)


@pytest.fixture
def prefs():
    return load_preferences()
