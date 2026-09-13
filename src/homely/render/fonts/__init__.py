"""Bundled bitmap fonts and the font registry.

Fonts live in ``data/`` as BDF files. Users can add their own by dropping ``*.bdf`` files
into ``<config_dir>/fonts`` and calling :func:`add_font_dir` (done by the app at startup).
"""

from __future__ import annotations

from functools import lru_cache
from pathlib import Path

from homely.render.fonts.bdf import BdfParseError, BitmapFont, Glyph, parse_bdf

__all__ = [
    "FONTS",
    "BdfParseError",
    "BitmapFont",
    "Glyph",
    "add_font_dir",
    "available_fonts",
    "get_font",
]

_DATA_DIR = Path(__file__).parent / "data"
_extra_dirs: list[Path] = []

# Bundled font names -> short descriptions (all monospace X11 misc-fixed except tom-thumb).
FONTS: dict[str, str] = {
    "tom-thumb": "3x5 tiny (4px advance, 6px line)",
    "4x6": "4x6 tiny",
    "5x7": "5x7 small",
    "5x8": "5x8 small",
    "6x9": "6x9 small",
    "6x10": "6x10 regular",
    "6x12": "6x12 regular",
    "6x13": "6x13 regular",
    "6x13B": "6x13 bold",
    "7x13": "7x13 regular",
    "7x13B": "7x13 bold",
    "8x13": "8x13 regular",
    "9x15": "9x15 medium",
    "9x18": "9x18 medium",
    "10x20": "10x20 large",
}


def add_font_dir(path: Path) -> None:
    """Register an extra directory of BDF fonts (searched before bundled ones)."""
    if path not in _extra_dirs:
        _extra_dirs.insert(0, path)
        get_font.cache_clear()


def _resolve(name: str) -> Path:
    filename = name if name.endswith(".bdf") else f"{name}.bdf"
    for d in [*_extra_dirs, _DATA_DIR]:
        candidate = d / filename
        if candidate.exists():
            return candidate
    raise KeyError(f"Unknown font {name!r}. Available: {', '.join(available_fonts())}")


def available_fonts() -> list[str]:
    names: set[str] = set()
    for d in [*_extra_dirs, _DATA_DIR]:
        if d.is_dir():
            names.update(p.stem for p in d.glob("*.bdf"))
    return sorted(names)


@lru_cache(maxsize=64)
def get_font(name: str) -> BitmapFont:
    """Load (and cache) a font by bundled name or extra-dir filename stem."""
    return parse_bdf(_resolve(name))
