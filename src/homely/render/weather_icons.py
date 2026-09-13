"""Weather icons in the spirit of the Wii Forecast Channel: bold, flat, friendly shapes.

Everything is drawn procedurally from circles and rectangles so icons look right at
8, 16, 24 or 32 pixels and there are no image assets to license.

``draw_weather_icon(canvas, x, y, size, kind, is_day=True)``
kinds: clear, partly, cloudy, fog, drizzle, rain, heavy_rain, snow, sleet, thunder, hail
"""

from __future__ import annotations

from typing import Literal

from homely.render.canvas import Canvas
from homely.render.color import Color

IconKind = Literal[
    "clear", "partly", "cloudy", "fog", "drizzle", "rain", "heavy_rain", "snow", "sleet", "thunder", "hail"
]
ICON_KINDS: tuple[IconKind, ...] = (
    "clear",
    "partly",
    "cloudy",
    "fog",
    "drizzle",
    "rain",
    "heavy_rain",
    "snow",
    "sleet",
    "thunder",
    "hail",
)

SUN: Color = (255, 190, 0)
SUN_CORE: Color = (255, 230, 90)
MOON: Color = (240, 236, 200)
MOON_SHADE: Color = (170, 165, 130)
CLOUD: Color = (240, 244, 255)
CLOUD_SHADE: Color = (150, 175, 215)
DARK_CLOUD: Color = (120, 130, 160)
DARK_CLOUD_SHADE: Color = (70, 78, 105)
RAIN: Color = (60, 150, 255)
SNOW: Color = (230, 245, 255)
BOLT: Color = (255, 230, 40)
FOG: Color = (170, 185, 210)
HAIL: Color = (200, 235, 255)


def _fill_circle(c: Canvas, cx: float, cy: float, r: float, color: Color) -> None:
    """Filled circle; cx, cy may be half-integers for even diameters."""
    r2 = r * r
    y0, y1 = int(cy - r) - 1, int(cy + r) + 1
    x0, x1 = int(cx - r) - 1, int(cx + r) + 1
    for y in range(y0, y1 + 1):
        for x in range(x0, x1 + 1):
            if (x + 0.5 - cx) ** 2 + (y + 0.5 - cy) ** 2 <= r2:
                c.pixel(x, y, color)


def _sun(c: Canvas, cx: float, cy: float, r: float, *, rays: bool = True) -> None:
    if rays:
        ray_len = max(1, round(r * 0.55))
        gap = max(1, round(r * 0.35))
        thick = 2 if r >= 6 else 1
        # 4 straight rays
        for dx, dy in ((1, 0), (-1, 0), (0, 1), (0, -1)):
            for i in range(ray_len):
                d = r + gap + i
                px, py = cx + dx * d, cy + dy * d
                c.rect(int(px - thick / 2), int(py - thick / 2), thick, thick, fill=SUN)
        # 4 diagonal rays
        diag = 0.7071
        for dx, dy in ((1, 1), (-1, 1), (1, -1), (-1, -1)):
            for i in range(ray_len):
                d = r + gap + i
                px, py = cx + dx * diag * d, cy + dy * diag * d
                c.rect(int(px - thick / 2), int(py - thick / 2), thick, thick, fill=SUN)
    _fill_circle(c, cx, cy, r, SUN)
    if r >= 5:
        _fill_circle(c, cx, cy, r - max(1.5, r * 0.3), SUN_CORE)


def _moon(c: Canvas, cx: float, cy: float, r: float) -> None:
    """Crescent: pixels inside the outer disc but outside an offset disc (never paints the cutout)."""
    if r < 3:
        _fill_circle(c, cx, cy, r, MOON)
    else:
        ir = r - max(1.0, r * 0.25)
        icx, icy = cx - r * 0.3, cy - r * 0.3
        for y in range(int(cy - r) - 1, int(cy + r) + 2):
            for x in range(int(cx - r) - 1, int(cx + r) + 2):
                px, py = x + 0.5, y + 0.5
                if (px - cx) ** 2 + (py - cy) ** 2 <= r * r and (px - icx) ** 2 + (py - icy) ** 2 > ir * ir:
                    c.pixel(x, y, MOON)
    # tiny star
    if r >= 5:
        sx, sy = int(cx - r * 1.15), int(cy - r * 0.9)
        c.pixel(sx, sy, MOON)
        c.pixel(sx - 1, sy, MOON_SHADE)
        c.pixel(sx + 1, sy, MOON_SHADE)
        c.pixel(sx, sy - 1, MOON_SHADE)
        c.pixel(sx, sy + 1, MOON_SHADE)


def _cloud(c: Canvas, x: int, y: int, w: int, h: int, color: Color, shade: Color) -> None:
    """Puffy cloud filling roughly the box (x, y, w, h): flat bottom, three bumps, shaded underside."""
    if w < 6 or h < 4:
        c.rect(x, y + h // 3, w, h - h // 3, fill=color)
        return
    base_y = y + h  # exclusive bottom
    r_big = h * 0.6
    r_left = h * 0.36
    r_right = h * 0.45
    cx_big = x + w * 0.4
    cy_big = base_y - r_big
    cx_left = x + r_left
    cy_left = base_y - r_left
    cx_right = x + w - r_right
    cy_right = base_y - r_right
    shade_rows = max(1, round(h * 0.18))
    for col, sh in ((color, False), (shade, True)):
        sub = c if not sh else c.sub(0, 0, c.width, c.height)
        if sh:
            # shade: only the bottom rows of the cloud shape
            sub = c.sub(0, base_y - shade_rows, c.width, shade_rows)
            sub_y_off = base_y - shade_rows
        else:
            sub_y_off = 0
        _fill_circle(sub, cx_big, cy_big - sub_y_off, r_big, col)
        _fill_circle(sub, cx_left, cy_left - sub_y_off, r_left, col)
        _fill_circle(sub, cx_right, cy_right - sub_y_off, r_right, col)
        sub.rect(int(cx_left), int(base_y - r_left - sub_y_off), int(cx_right - cx_left) + 1, int(r_left), fill=col)


def _drops(c: Canvas, x: int, y: int, w: int, n: int, size: int, color: Color = RAIN) -> None:
    """n slanted drops spread across width w, starting at y (each `size` px tall)."""
    if n <= 0:
        return
    step = w / n
    for i in range(n):
        dx = int(x + step * i + step / 2) - (1 if size > 1 else 0)
        stagger = (i % 2) * max(1, size // 2)
        for k in range(size):
            c.pixel(dx + (size - 1 - k) // max(1, size - 1) if size > 2 else dx, y + stagger + k, color)


def _flakes(c: Canvas, x: int, y: int, w: int, n: int, big: bool) -> None:
    step = w / n
    for i in range(n):
        fx = int(x + step * i + step / 2)
        fy = y + (i % 2) * (2 if big else 1)
        c.pixel(fx, fy, SNOW)
        if big:
            c.pixel(fx - 1, fy, SNOW)
            c.pixel(fx + 1, fy, SNOW)
            c.pixel(fx, fy - 1, SNOW)
            c.pixel(fx, fy + 1, SNOW)


def _bolt(c: Canvas, x: int, y: int, h: int) -> None:
    """Lightning bolt, h px tall, zig to the left then right."""
    if h <= 3:
        for k in range(h):
            c.pixel(x - (k // 2), y + k, BOLT)
        return
    top = h // 2
    for k in range(top):
        c.pixel(x - k // 2, y + k, BOLT)
        c.pixel(x - k // 2 + 1, y + k, BOLT)
    mid_x = x - (top - 1) // 2
    c.hline(mid_x, y + top - 1, 3 if h >= 6 else 2, BOLT)
    for k in range(top, h):
        px = mid_x + 2 - (k - top) // 2
        c.pixel(px, y + k, BOLT)
        if h >= 8 and k < h - 1:
            c.pixel(px - 1, y + k, BOLT)


def draw_weather_icon(canvas: Canvas, x: int, y: int, size: int, kind: str, *, is_day: bool = True) -> None:
    """Draw a `size` x `size` icon with its top-left at (x, y)."""
    c = canvas.sub(x, y, size, size)
    s = size
    if kind == "clear":
        if is_day:
            _sun(c, s / 2, s / 2, s * 0.27)
        else:
            _moon(c, s / 2, s / 2, s * 0.32)
        return
    dark = kind in ("thunder", "heavy_rain")
    cloud_col, cloud_shade = (DARK_CLOUD, DARK_CLOUD_SHADE) if dark else (CLOUD, CLOUD_SHADE)
    precip_rows = 0 if kind in ("cloudy", "partly") else max(2, round(s * 0.3))
    cloud_h = max(4, round(s * (0.5 if kind == "partly" else 0.55)))
    cloud_w = s if kind != "partly" else max(6, round(s * 0.78))
    cloud_y = s - precip_rows - cloud_h if kind != "partly" else s - cloud_h - max(0, round(s * 0.05))
    cloud_x = 0 if kind != "partly" else s - cloud_w
    if kind == "partly":
        # sun (or moon) peeking out top-left, cloud in front bottom-right
        if is_day:
            _sun(c, s * 0.34, s * 0.34, s * 0.2)
        else:
            _moon(c, s * 0.34, s * 0.36, s * 0.22)
    _cloud(c, cloud_x, cloud_y, cloud_w, cloud_h, cloud_col, cloud_shade)
    if kind == "fog":
        for i in range(2 if s < 12 else 3):
            yy = cloud_y + cloud_h + 1 + i * 2
            if yy < s:
                c.hline(1 + i, yy, s - 2 - i * 2, FOG)
        return
    py = cloud_y + cloud_h + (1 if s >= 12 else 0)
    drop_size = 1 if s < 12 else (2 if s < 20 else 3)
    if kind == "drizzle":
        _drops(c, 1, py + 1, s - 2, 2 if s < 12 else 3, drop_size)
    elif kind == "rain":
        _drops(c, 1, py, s - 2, 3 if s < 20 else 4, drop_size)
    elif kind == "heavy_rain":
        _drops(c, 0, py, s, 4 if s < 20 else 5, drop_size)
        if s >= 16:
            _drops(c, 2, py + drop_size + 1, s - 4, 3, drop_size)
    elif kind == "snow":
        _flakes(c, 1, py + (1 if s >= 12 else 0), s - 2, 2 if s < 12 else 3, big=s >= 16)
    elif kind == "sleet":
        _drops(c, 1, py, s // 2 - 1, 1 if s < 12 else 2, drop_size)
        _flakes(c, s // 2, py + (1 if s >= 12 else 0), s // 2 - 1, 1 if s < 12 else 2, big=s >= 16)
    elif kind == "hail":
        step = (s - 2) / (3 if s < 20 else 4)
        for i in range(3 if s < 20 else 4):
            hx = int(1 + step * i + step / 2)
            hy = py + (i % 2)
            if s >= 16:
                c.rect(hx - 1, hy, 2, 2, fill=HAIL)
            else:
                c.pixel(hx, hy, HAIL)
    elif kind == "thunder":
        bolt_h = max(3, precip_rows + (2 if s >= 16 else 1))
        _bolt(c, int(s * 0.55), s - bolt_h, bolt_h)
        if s >= 20:
            _drops(c, 1, py, s // 3, 1, drop_size)
