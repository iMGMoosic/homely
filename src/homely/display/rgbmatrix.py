"""RgbMatrixDisplay: the hzeller rpi-rgb-led-matrix backend.

The ``rgbmatrix`` module is imported lazily so homely runs anywhere without it.
Constructing RGBMatrix requires root; the library then drops to drop_priv_user.
"""

from __future__ import annotations

import contextlib
import importlib
import logging
from typing import Any

from PIL import Image

from homely.config.models import PanelConfig
from homely.render.gamma import build_lut
from homely.render.size import Orientation, Size

log = logging.getLogger(__name__)

OPTION_FIELDS = (
    "rows",
    "cols",
    "chain_length",
    "parallel",
    "hardware_mapping",
    "gpio_slowdown",
    "pwm_bits",
    "pwm_lsb_nanoseconds",
    "pwm_dither_bits",
    "led_rgb_sequence",
    "panel_type",
    "multiplexing",
    "row_address_type",
    "scan_mode",
    "limit_refresh_rate_hz",
    "disable_hardware_pulsing",
    "inverse_colors",
    "show_refresh_rate",
    "drop_privileges",
    "drop_priv_user",
    "drop_priv_group",
)


def rgbmatrix_available() -> bool:
    try:
        importlib.import_module("rgbmatrix")
    except ImportError:
        return False
    return True


def pixel_mapper_for(cfg: PanelConfig) -> str:
    mappers = [m for m in cfg.pixel_mapper_config.split(";") if m.strip()]
    if cfg.orientation is Orientation.PORTRAIT:
        mappers.append(f"Rotate:{cfg.rotate_direction}")
    return ";".join(mappers)


class RgbMatrixDisplay:
    def __init__(self, cfg: PanelConfig, initial_brightness: int = 60) -> None:
        self.cfg = cfg
        self.size: Size = cfg.logical
        self._lut: list[int] | None = None if abs(cfg.gamma - 1.0) < 1e-6 else list(build_lut(cfg.gamma))
        self._matrix: Any = None
        self._back: Any = None
        self._initial_brightness = initial_brightness

    def build_options(self) -> Any:
        rgbmatrix = importlib.import_module("rgbmatrix")
        options = rgbmatrix.RGBMatrixOptions()
        for name in OPTION_FIELDS:
            setattr(options, name, getattr(self.cfg, name))
        options.pixel_mapper_config = pixel_mapper_for(self.cfg)
        options.brightness = max(1, min(100, self._initial_brightness))
        return options

    def open(self) -> None:
        rgbmatrix = importlib.import_module("rgbmatrix")
        options = self.build_options()
        self._matrix = rgbmatrix.RGBMatrix(options=options)
        got = Size(int(self._matrix.width), int(self._matrix.height))
        if got != self.size:
            raise RuntimeError(
                f"matrix reports {got} but config expects {self.size}; check rows/cols/chain/parallel/orientation"
            )
        self._back = self._matrix.CreateFrameCanvas()
        log.info("rgbmatrix opened: %s mapping=%s slowdown=%d", got, self.cfg.hardware_mapping, self.cfg.gpio_slowdown)

    def show(self, frame: Image.Image) -> None:
        if self._matrix is None:
            return
        if frame.mode != "RGB":
            frame = frame.convert("RGB")
        if self._lut is not None:
            frame = frame.point(self._lut)
        self._back.SetImage(frame, 0, 0, True)
        self._back = self._matrix.SwapOnVSync(self._back)

    def set_brightness(self, level: int) -> None:
        if self._matrix is not None:
            self._matrix.brightness = max(0, min(100, level))

    def close(self) -> None:
        if self._matrix is not None:
            with contextlib.suppress(Exception):
                self._matrix.Clear()
            self._matrix = None
            self._back = None
