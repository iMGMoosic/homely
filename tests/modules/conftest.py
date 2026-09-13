"""Module goldens are rendered with the shipped default look (14-segment text)."""

from __future__ import annotations

import pytest

from homely.render.fonts import set_theme


@pytest.fixture(autouse=True)
def segment_theme():
    set_theme("segment")
    yield
    set_theme("pixel")
