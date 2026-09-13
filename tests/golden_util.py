"""Golden-image helper: exact pixel comparison, with --update-golden to rewrite."""

from __future__ import annotations

from pathlib import Path

import pytest
from PIL import Image, ImageChops

GOLDEN_DIR = Path(__file__).parent / "golden"
OUT_DIR = Path(__file__).parent / ".golden_out"


def assert_golden(image: Image.Image, name: str, request: pytest.FixtureRequest) -> None:
    path = GOLDEN_DIR / f"{name}.png"
    update = request.config.getoption("--update-golden")
    if update or not path.exists():
        path.parent.mkdir(parents=True, exist_ok=True)
        image.save(path)
        if not update:
            pytest.skip(f"golden created: {path.relative_to(GOLDEN_DIR.parent)} (re-run to compare)")
        return
    expected = Image.open(path).convert("RGB")
    if expected.size != image.size or ImageChops.difference(expected, image.convert("RGB")).getbbox():
        OUT_DIR.mkdir(parents=True, exist_ok=True)
        actual_path = OUT_DIR / f"{name.replace('/', '_')}.actual.png"
        image.save(actual_path)
        w = max(expected.width, image.width)
        h = max(expected.height, image.height)
        strip = Image.new("RGB", (w * 3 + 4, h), (60, 0, 60))
        strip.paste(expected, (0, 0))
        strip.paste(image, (w + 2, 0))
        strip.paste(ImageChops.difference(expected, image.convert("RGB")), (2 * w + 4, 0))
        strip.resize((strip.width * 4, strip.height * 4), Image.Resampling.NEAREST).save(
            OUT_DIR / f"{name.replace('/', '_')}.diff.png"
        )
        pytest.fail(f"golden mismatch for {name}; see {actual_path} (run pytest --update-golden to accept)")
