"""A tiny software 3D renderer for idle animations: vectors, matrices, a perspective camera,
wireframes, flat-shaded meshes (painter's order) and an incremental depth buffer.

Pure Python; scenes stay in the hundreds of vertices so a 64x64..128x128 frame is cheap.
"""

from __future__ import annotations

import math
from dataclasses import dataclass, field

from homely.render.canvas import Canvas
from homely.render.color import Color, dim

Vec3 = tuple[float, float, float]
Mat4 = tuple[tuple[float, ...], ...]


def v_add(a: Vec3, b: Vec3) -> Vec3:
    return (a[0] + b[0], a[1] + b[1], a[2] + b[2])


def v_sub(a: Vec3, b: Vec3) -> Vec3:
    return (a[0] - b[0], a[1] - b[1], a[2] - b[2])


def v_scale(a: Vec3, s: float) -> Vec3:
    return (a[0] * s, a[1] * s, a[2] * s)


def v_dot(a: Vec3, b: Vec3) -> float:
    return a[0] * b[0] + a[1] * b[1] + a[2] * b[2]


def v_cross(a: Vec3, b: Vec3) -> Vec3:
    return (a[1] * b[2] - a[2] * b[1], a[2] * b[0] - a[0] * b[2], a[0] * b[1] - a[1] * b[0])


def v_norm(a: Vec3) -> Vec3:
    n = math.sqrt(v_dot(a, a)) or 1.0
    return (a[0] / n, a[1] / n, a[2] / n)


def m_identity() -> Mat4:
    return ((1, 0, 0, 0), (0, 1, 0, 0), (0, 0, 1, 0), (0, 0, 0, 1))


def m_mul(a: Mat4, b: Mat4) -> Mat4:
    return tuple(tuple(sum(a[i][k] * b[k][j] for k in range(4)) for j in range(4)) for i in range(4))


def m_translate(x: float, y: float, z: float) -> Mat4:
    return ((1, 0, 0, x), (0, 1, 0, y), (0, 0, 1, z), (0, 0, 0, 1))


def m_scale(s: float) -> Mat4:
    return ((s, 0, 0, 0), (0, s, 0, 0), (0, 0, s, 0), (0, 0, 0, 1))


def m_rot_x(a: float) -> Mat4:
    c, s = math.cos(a), math.sin(a)
    return ((1, 0, 0, 0), (0, c, -s, 0), (0, s, c, 0), (0, 0, 0, 1))


def m_rot_y(a: float) -> Mat4:
    c, s = math.cos(a), math.sin(a)
    return ((c, 0, s, 0), (0, 1, 0, 0), (-s, 0, c, 0), (0, 0, 0, 1))


def m_rot_z(a: float) -> Mat4:
    c, s = math.cos(a), math.sin(a)
    return ((c, -s, 0, 0), (s, c, 0, 0), (0, 0, 1, 0), (0, 0, 0, 1))


def m_apply(m: Mat4, v: Vec3) -> Vec3:
    x, y, z = v
    return (
        m[0][0] * x + m[0][1] * y + m[0][2] * z + m[0][3],
        m[1][0] * x + m[1][1] * y + m[1][2] * z + m[1][3],
        m[2][0] * x + m[2][1] * y + m[2][2] * z + m[2][3],
    )


@dataclass
class Camera:
    """Looks down +z from the origin; ``focal`` is the projection distance in pixels."""

    width: int
    height: int
    focal: float = 60.0
    near: float = 0.1

    def project(self, p: Vec3) -> tuple[float, float, float] | None:
        """(screen x, screen y, depth) or None when behind the near plane."""
        x, y, z = p
        if z <= self.near:
            return None
        s = self.focal / z
        return (self.width / 2 + x * s, self.height / 2 - y * s, z)


@dataclass
class Mesh:
    vertices: list[Vec3]
    faces: list[tuple[int, ...]]  # indices, counter-clockwise seen from outside
    colors: list[Color] = field(default_factory=list)  # per face; empty = single color

    @staticmethod
    def cube(size: float = 1.0) -> Mesh:
        s = size / 2
        v: list[Vec3] = [
            (-s, -s, -s),
            (s, -s, -s),
            (s, s, -s),
            (-s, s, -s),
            (-s, -s, s),
            (s, -s, s),
            (s, s, s),
            (-s, s, s),
        ]
        f: list[tuple[int, ...]] = [(0, 3, 2, 1), (4, 5, 6, 7), (0, 1, 5, 4), (2, 3, 7, 6), (1, 2, 6, 5), (0, 4, 7, 3)]
        return Mesh(v, f)

    @staticmethod
    def torus(r_major: float = 1.0, r_minor: float = 0.4, n_major: int = 16, n_minor: int = 8) -> Mesh:
        verts: list[Vec3] = []
        for i in range(n_major):
            a = 2 * math.pi * i / n_major
            for j in range(n_minor):
                b = 2 * math.pi * j / n_minor
                r = r_major + r_minor * math.cos(b)
                verts.append((r * math.cos(a), r_minor * math.sin(b), r * math.sin(a)))
        faces: list[tuple[int, ...]] = []
        for i in range(n_major):
            for j in range(n_minor):
                a, b = i * n_minor + j, i * n_minor + (j + 1) % n_minor
                c, d = ((i + 1) % n_major) * n_minor + (j + 1) % n_minor, ((i + 1) % n_major) * n_minor + j
                faces.append((a, b, c, d))
        return Mesh(verts, faces)


def shade(color: Color, normal: Vec3, light: Vec3, ambient: float = 0.25) -> Color:
    lam = max(0.0, v_dot(v_norm(normal), v_norm(light)))
    return dim(color, min(1.0, ambient + (1 - ambient) * lam))


def face_normal(a: Vec3, b: Vec3, c: Vec3) -> Vec3:
    return v_cross(v_sub(b, a), v_sub(c, a))


def draw_wireframe(canvas: Canvas, cam: Camera, mesh: Mesh, transform: Mat4, color: Color) -> None:
    pts = [cam.project(m_apply(transform, v)) for v in mesh.vertices]
    seen: set[tuple[int, int]] = set()
    for face in mesh.faces:
        for i in range(len(face)):
            a, b = face[i], face[(i + 1) % len(face)]
            key = (min(a, b), max(a, b))
            if key in seen:
                continue
            seen.add(key)
            pa, pb = pts[a], pts[b]
            if pa is None or pb is None:
                continue
            canvas.line(round(pa[0]), round(pa[1]), round(pb[0]), round(pb[1]), color)


def draw_mesh(
    canvas: Canvas,
    cam: Camera,
    mesh: Mesh,
    transform: Mat4,
    color: Color,
    light: Vec3 = (-0.4, 0.8, -0.6),
    *,
    cull: bool = True,
) -> None:
    """Flat-shaded fill, back to front (painter's algorithm)."""
    world = [m_apply(transform, v) for v in mesh.vertices]
    pts = [cam.project(v) for v in world]
    order: list[tuple[float, int]] = []
    for idx, face in enumerate(mesh.faces):
        if any(pts[i] is None for i in face):
            continue
        depth = sum(world[i][2] for i in face) / len(face)
        order.append((depth, idx))
    order.sort(reverse=True)
    from PIL import ImageDraw

    draw = ImageDraw.Draw(canvas.image)
    ox, oy = canvas._abs(0, 0)
    for _, idx in order:
        face = mesh.faces[idx]
        a, b, c = world[face[0]], world[face[1]], world[face[2]]
        normal = face_normal(a, b, c)
        if cull and v_dot(normal, a) > 0:  # facing away from the camera at the origin
            continue
        col = mesh.colors[idx] if mesh.colors else color
        poly = [(ox + pts[i][0], oy + pts[i][1]) for i in face]  # type: ignore[index]
        draw.polygon(poly, fill=shade(col, normal, light))


class DepthBuffer:
    """Per-pixel depth for scenes drawn incrementally (draw once, keep forever)."""

    def __init__(self, width: int, height: int) -> None:
        self.width, self.height = width, height
        self.z = [math.inf] * (width * height)

    def clear(self) -> None:
        self.z = [math.inf] * (self.width * self.height)

    def fill_polygon(self, canvas: Canvas, pts: list[tuple[float, float, float]], color: Color) -> None:
        """Fill a convex screen-space polygon (x, y, depth) with a depth test per pixel."""
        if len(pts) < 3:
            return
        ys = [p[1] for p in pts]
        y0, y1 = max(0, math.floor(min(ys))), min(self.height - 1, math.ceil(max(ys)))
        n = len(pts)
        for y in range(y0, y1 + 1):
            yc = y + 0.5
            xs: list[tuple[float, float]] = []
            for i in range(n):
                (xa, ya, za), (xb, yb, zb) = pts[i], pts[(i + 1) % n]
                if (ya <= yc < yb) or (yb <= yc < ya):
                    t = (yc - ya) / (yb - ya)
                    xs.append((xa + (xb - xa) * t, za + (zb - za) * t))
            if len(xs) < 2:
                continue
            xs.sort()
            (xl, zl), (xr, zr) = xs[0], xs[-1]
            xa0, xa1 = max(0, math.floor(xl + 0.5)), min(self.width - 1, math.floor(xr - 0.5))
            if xa1 < xa0:
                xa1 = xa0 = round((xl + xr) / 2)
                if not 0 <= xa0 < self.width:
                    continue
            span = (xr - xl) or 1.0
            row = y * self.width
            for x in range(xa0, xa1 + 1):
                z = zl + (zr - zl) * ((x + 0.5 - xl) / span)
                if z < self.z[row + x]:
                    self.z[row + x] = z
                    canvas.pixel(x, y, color)
