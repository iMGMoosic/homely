"""Input events (USB game controllers). The hub implementation lands with the game module."""

from __future__ import annotations

from dataclasses import dataclass
from enum import Enum


class Button(str, Enum):
    UP = "up"
    DOWN = "down"
    LEFT = "left"
    RIGHT = "right"
    A = "a"
    B = "b"
    X = "x"
    Y = "y"
    START = "start"
    SELECT = "select"
    L = "l"
    R = "r"


@dataclass(frozen=True)
class InputEvent:
    button: Button
    pressed: bool
    device: str = ""
    value: float = 0.0  # analog magnitude for sticks, 0..1
