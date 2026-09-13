"""Bundled bitmap fonts and the font registry.

Fonts live in ``data/`` as BDF files. Users can add their own by dropping ``*.bdf`` files
into ``<config_dir>/fonts`` and calling :func:`add_font_dir` (done by the app at startup).
"""

from __future__ import annotations

from functools import lru_cache
from pathlib import Path
from typing import Literal

from homely.render.fonts.bdf import BdfParseError, BitmapFont, Glyph, parse_bdf
from homely.render.fonts.segment14 import segment_font

FontTheme = Literal["segment", "pixel"]

__all__ = [
    "FONTS",
    "SEGMENT_MAP",
    "BdfParseError",
    "BitmapFont",
    "FontTheme",
    "Glyph",
    "add_font_dir",
    "available_fonts",
    "get_font",
    "get_theme",
    "segment_font",
    "set_theme",
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
        _get_bdf.cache_clear()


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


# Pixel-font name -> 14-segment cell (w, h, thickness, gap, line height) used when the
# "segment" theme is active. The tiny fonts get a 4 px cell: cramped but still readable,
# and it keeps the whole display in one style. Use "pixel:<name>" to force a bitmap font.
SEGMENT_MAP: dict[str, tuple[int, int, int, int, int]] = {
    "tom-thumb": (4, 6, 1, 1, 7),
    "4x6": (4, 6, 1, 1, 7),
    "5x7": (5, 7, 1, 1, 8),
    "5x8": (5, 7, 1, 1, 8),
    "6x9": (5, 9, 1, 1, 10),
    "6x10": (5, 9, 1, 1, 10),
    "6x12": (5, 11, 1, 1, 13),
    "6x13": (5, 11, 1, 1, 13),
    "6x13B": (5, 11, 1, 1, 13),
    "7x13": (5, 11, 1, 2, 13),
    "7x13B": (5, 11, 1, 2, 13),
    "8x13": (7, 11, 1, 1, 13),
    "9x15": (7, 13, 1, 2, 15),
    "9x18": (7, 15, 1, 2, 18),
    "10x20": (9, 17, 2, 1, 20),
}

_theme: FontTheme = "pixel"


def set_theme(theme: FontTheme) -> None:
    """Choose the program-wide look: 'segment' (14-segment display) or 'pixel' (bitmap fonts)."""
    global _theme
    _theme = theme


def get_theme() -> FontTheme:
    return _theme


def get_font(name: str) -> BitmapFont:
    """Font by name, honoring the active theme. 'seg:WxH' / 'seg:WxH:T' force a segment font."""
    if name.startswith("seg:"):
        parts = name.split(":")[1:]
        w, h = (int(v) for v in parts[0].split("x"))
        t = int(parts[1]) if len(parts) > 1 else 1
        return segment_font(w, h, t)
    if name.startswith("pixel:"):
        return _get_bdf(name[len("pixel:") :])
    if _theme == "segment" and name in SEGMENT_MAP:
        w, h, t, gap, lh = SEGMENT_MAP[name]
        return segment_font(w, h, t, gap, lh)
    return _get_bdf(name)


@lru_cache(maxsize=64)
def _get_bdf(name: str) -> BitmapFont:
    """Load (and cache) a BDF font by bundled name or extra-dir filename stem."""
    return parse_bdf(_resolve(name))
