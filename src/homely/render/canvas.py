"""Canvas: the drawing surface handed to modules.

A thin wrapper over a Pillow RGB image with an origin offset and clip rectangle so
sub-canvases are cheap views onto the same pixels.
"""

from __future__ import annotations

from typing import Literal

from PIL import Image, ImageDraw

from homely.render.color import BLACK, Color
from homely.render.fonts.bdf import BitmapFont
from homely.render.size import Size

HAlign = Literal["left", "center", "right"]
VAlign = Literal["top", "middle", "bottom", "baseline"]


class Canvas:
    __slots__ = ("_clip", "_draw", "_ox", "_oy", "image", "size")

    def __init__(
        self,
        size: Size,
        *,
        image: Image.Image | None = None,
        origin: tuple[int, int] = (0, 0),
        clip: tuple[int, int, int, int] | None = None,
    ) -> None:
        self.size = size
        if image is None:
            image = Image.new("RGB", size.as_tuple(), BLACK)
        self.image = image
        self._ox, self._oy = origin
        # clip is (x0, y0, x1, y1) in absolute image coordinates, exclusive end.
        self._clip = clip if clip is not None else (0, 0, image.width, image.height)
        self._draw = ImageDraw.Draw(image)

    # ---- geometry -------------------------------------------------------------

    @property
    def width(self) -> int:
        return self.size.w

    @property
    def height(self) -> int:
        return self.size.h

    def sub(self, x: int, y: int, w: int, h: int) -> Canvas:
        """A clipped, translated view of this canvas (shares pixels)."""
        ax, ay = self._ox + x, self._oy + y
        cx0 = max(self._clip[0], ax)
        cy0 = max(self._clip[1], ay)
        cx1 = min(self._clip[2], ax + w)
        cy1 = min(self._clip[3], ay + h)
        if cx1 <= cx0 or cy1 <= cy0:
            cx1, cy1 = cx0, cy0
        return Canvas(Size(max(w, 1), max(h, 1)), image=self.image, origin=(ax, ay), clip=(cx0, cy0, cx1, cy1))

    def _abs(self, x: int, y: int) -> tuple[int, int]:
        return self._ox + x, self._oy + y

    def _visible_box(self, x0: int, y0: int, x1: int, y1: int) -> tuple[int, int, int, int] | None:
        """Intersect an absolute exclusive box with the clip; None if empty."""
        bx0, by0 = max(x0, self._clip[0]), max(y0, self._clip[1])
        bx1, by1 = min(x1, self._clip[2]), min(y1, self._clip[3])
        if bx1 <= bx0 or by1 <= by0:
            return None
        return bx0, by0, bx1, by1

    # ---- primitives -----------------------------------------------------------

    def clear(self, color: Color = BLACK) -> None:
        box = self._visible_box(self._ox, self._oy, self._ox + self.width, self._oy + self.height)
        if box:
            self._draw.rectangle((box[0], box[1], box[2] - 1, box[3] - 1), fill=color)

    def pixel(self, x: int, y: int, color: Color) -> None:
        ax, ay = self._abs(x, y)
        if self._clip[0] <= ax < self._clip[2] and self._clip[1] <= ay < self._clip[3]:
            self.image.putpixel((ax, ay), color)

    def get_pixel(self, x: int, y: int) -> Color:
        ax, ay = self._abs(x, y)
        r, g, b = self.image.getpixel((ax, ay))[:3]  # type: ignore[index]
        return (r, g, b)

    def rect(
        self,
        x: int,
        y: int,
        w: int,
        h: int,
        *,
        fill: Color | None = None,
        outline: Color | None = None,
    ) -> None:
        if w <= 0 or h <= 0:
            return
        ax, ay = self._abs(x, y)
        if outline is not None and fill is None:
            # Draw the four edges as clipped lines so partial outlines clip correctly.
            self.hline(x, y, w, outline)
            self.hline(x, y + h - 1, w, outline)
            self.vline(x, y, h, outline)
            self.vline(x + w - 1, y, h, outline)
            return
        box = self._visible_box(ax, ay, ax + w, ay + h)
        if box is None:
            return
        if fill is not None:
            self._draw.rectangle((box[0], box[1], box[2] - 1, box[3] - 1), fill=fill)
        if outline is not None:
            self.rect(x, y, w, h, outline=outline)

    def hline(self, x: int, y: int, length: int, color: Color) -> None:
        ax, ay = self._abs(x, y)
        box = self._visible_box(ax, ay, ax + length, ay + 1)
        if box:
            self._draw.line((box[0], box[1], box[2] - 1, box[1]), fill=color)

    def vline(self, x: int, y: int, length: int, color: Color) -> None:
        ax, ay = self._abs(x, y)
        box = self._visible_box(ax, ay, ax + 1, ay + length)
        if box:
            self._draw.line((box[0], box[1], box[0], box[3] - 1), fill=color)

    def line(self, x0: int, y0: int, x1: int, y1: int, color: Color) -> None:
        """Bresenham line, clipped per pixel (lines are short on LED panels)."""
        dx, dy = abs(x1 - x0), -abs(y1 - y0)
        sx = 1 if x0 < x1 else -1
        sy = 1 if y0 < y1 else -1
        err = dx + dy
        x, y = x0, y0
        while True:
            self.pixel(x, y, color)
            if x == x1 and y == y1:
                break
            e2 = 2 * err
            if e2 >= dy:
                err += dy
                x += sx
            if e2 <= dx:
                err += dx
                y += sy

    def fill_gradient_v(self, top: Color, bottom: Color) -> None:
        from homely.render.color import lerp

        h = max(1, self.height - 1)
        for row in range(self.height):
            self.hline(0, row, self.width, lerp(top, bottom, row / h))

    def blit(self, img: Image.Image, x: int, y: int, *, mask: Image.Image | None = None) -> None:
        """Paste an image (RGB or RGBA) at (x, y). RGBA alpha is used as the mask."""
        ax, ay = self._abs(x, y)
        box = self._visible_box(ax, ay, ax + img.width, ay + img.height)
        if box is None:
            return
        crop = (box[0] - ax, box[1] - ay, box[2] - ax, box[3] - ay)
        src = img.crop(crop) if crop != (0, 0, img.width, img.height) else img
        if mask is not None:
            mask = mask.crop(crop) if crop != (0, 0, img.width, img.height) else mask
        elif src.mode == "RGBA":
            mask = src.getchannel("A")
            src = src.convert("RGB")
        elif src.mode != "RGB":
            src = src.convert("RGB")
        self.image.paste(src, (box[0], box[1]), mask)

    # ---- text -----------------------------------------------------------------

    def text(
        self,
        x: int,
        y: int,
        s: str,
        font: BitmapFont,
        color: Color,
        *,
        halign: HAlign = "left",
        valign: VAlign = "top",
    ) -> int:
        """Draw text with (x, y) as the anchor per halign/valign. Returns the text width.

        valign="top" means y is the top of the font's line box (ascent + descent);
        "baseline" means y is the baseline row.
        """
        width = font.measure(s)
        if halign == "center":
            x -= width // 2
        elif halign == "right":
            x -= width
        if valign == "top":
            baseline = y + font.ascent
        elif valign == "middle":
            baseline = y - font.line_height // 2 + font.ascent
        elif valign == "bottom":
            baseline = y - font.descent
        else:
            baseline = y
        cx = x
        for ch in s:
            g = font.glyph(ch)
            if g is None:
                cx += font.default_advance
                continue
            if g.width and g.height:
                gx = cx + g.x_off
                gy = baseline - g.y_off - g.height
                self._paste_mask(g.mask, gx, gy, color)
            cx += g.advance
        return width

    def text_centered(self, y: int, s: str, font: BitmapFont, color: Color) -> int:
        return self.text(self.width // 2, y, s, font, color, halign="center")

    def _paste_mask(self, mask: Image.Image, x: int, y: int, color: Color) -> None:
        ax, ay = self._abs(x, y)
        box = self._visible_box(ax, ay, ax + mask.width, ay + mask.height)
        if box is None:
            return
        crop = (box[0] - ax, box[1] - ay, box[2] - ax, box[3] - ay)
        m = mask.crop(crop) if crop != (0, 0, mask.width, mask.height) else mask
        self.image.paste(color, (box[0], box[1]), m)

    # ---- output ---------------------------------------------------------------

    def snapshot(self) -> Image.Image:
        """A copy of this canvas region as a standalone RGB image."""
        return self.image.crop((self._ox, self._oy, self._ox + self.width, self._oy + self.height))

    def upscaled(self, factor: int) -> Image.Image:
        return self.snapshot().resize((self.width * factor, self.height * factor), Image.Resampling.NEAREST)
