"""homely: a Tidbyt-like LED matrix display for Raspberry Pi."""

from importlib.metadata import PackageNotFoundError, version

try:
    __version__ = version("homely-display")
except PackageNotFoundError:  # running from a source checkout without install
    __version__ = "0.0.0+dev"

__all__ = ["__version__"]
