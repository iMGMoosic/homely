"""Per-size layout registration for modules.

Usage inside a Module subclass::

    @layout(64, 64)
    def render_square(self, canvas, frame): ...

    @layout_family(SizeFamily.WIDE, min_w=64)
    def render_wide(self, canvas, frame): ...

    @layout_fallback
    def render_any(self, canvas, frame): ...

``resolve(cls, size)`` picks the best renderer for a size.
"""

from __future__ import annotations

from collections.abc import Callable
from dataclasses import dataclass
from typing import Any

from homely.render.size import Size, SizeFamily

Renderer = Callable[[Any, Any, Any], None]

_MARK = "_homely_layouts"


@dataclass(frozen=True)
class _LayoutSpec:
    exact: tuple[Size, ...] = ()
    family: SizeFamily | None = None
    min_w: int = 0
    min_h: int = 0
    fallback: bool = False


def _mark(fn: Renderer, spec: _LayoutSpec) -> Renderer:
    specs: list[_LayoutSpec] = list(getattr(fn, _MARK, []))
    specs.append(spec)
    setattr(fn, _MARK, specs)
    return fn


def layout(w: int, h: int, *more: tuple[int, int]) -> Callable[[Renderer], Renderer]:
    """Register a renderer for one or more exact sizes."""
    sizes = (Size(w, h), *(Size(mw, mh) for mw, mh in more))

    def deco(fn: Renderer) -> Renderer:
        return _mark(fn, _LayoutSpec(exact=sizes))

    return deco


def layout_family(family: SizeFamily, *, min_w: int = 0, min_h: int = 0) -> Callable[[Renderer], Renderer]:
    """Register a renderer for every size in a family that meets the minimums."""

    def deco(fn: Renderer) -> Renderer:
        return _mark(fn, _LayoutSpec(family=family, min_w=min_w, min_h=min_h))

    return deco


def layout_fallback(fn: Renderer) -> Renderer:
    """Register a size-agnostic renderer used when nothing better matches."""
    return _mark(fn, _LayoutSpec(fallback=True))


class UnsupportedSize(LookupError):
    pass


@dataclass(frozen=True)
class Resolved:
    renderer: Renderer
    exact: bool
    designed_for: Size | None  # the size the renderer was written for, if exact
    fallback: bool


def collect(cls: type) -> list[tuple[Renderer, _LayoutSpec]]:
    out: list[tuple[Renderer, _LayoutSpec]] = []
    seen: set[int] = set()
    for klass in cls.__mro__:
        for name, attr in vars(klass).items():
            if name.startswith("__"):
                continue
            specs = getattr(attr, _MARK, None)
            if not specs or id(attr) in seen:
                continue
            seen.add(id(attr))
            for spec in specs:
                out.append((attr, spec))
    return out


def supported_sizes(cls: type, candidates: tuple[Size, ...]) -> list[Size]:
    """Which of candidates the class can render (via any rule)."""
    out = []
    for size in candidates:
        try:
            resolve(cls, size)
        except UnsupportedSize:
            continue
        out.append(size)
    return out


def resolve(cls: type, size: Size) -> Resolved:
    """Resolution order: exact -> largest same-family exact that fits -> family -> fallback."""
    entries = collect(cls)
    if not entries:
        raise UnsupportedSize(f"{cls.__name__} registers no layouts")

    for fn, spec in entries:
        if size in spec.exact:
            return Resolved(fn, exact=True, designed_for=size, fallback=False)

    best: tuple[int, Renderer, Size] | None = None
    for fn, spec in entries:
        for s in spec.exact:
            if s.family == size.family and s.fits_in(size) and (best is None or s.area > best[0]):
                best = (s.area, fn, s)
    if best is not None:
        return Resolved(best[1], exact=False, designed_for=best[2], fallback=False)

    for fn, spec in entries:
        if spec.family == size.family and size.w >= spec.min_w and size.h >= spec.min_h:
            return Resolved(fn, exact=False, designed_for=None, fallback=False)

    for fn, spec in entries:
        if spec.fallback:
            return Resolved(fn, exact=False, designed_for=None, fallback=True)

    raise UnsupportedSize(f"{cls.__name__} has no layout for {size}")
