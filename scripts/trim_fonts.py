"""Trim bundled BDF fonts to a useful Unicode subset to keep the wheel small.

Keeps glyphs in KEEP_RANGES (Latin, Greek, Cyrillic, punctuation, currency, arrows,
math, box drawing, geometric shapes, misc symbols). Run from the repo root:

    python scripts/trim_fonts.py
"""

from __future__ import annotations

import re
import sys
from pathlib import Path

# Inclusive codepoint ranges to keep.
KEEP_RANGES: tuple[tuple[int, int], ...] = (
    (0x0000, 0x024F),  # Basic Latin, Latin-1, Latin Extended-A/B
    (0x0370, 0x03FF),  # Greek
    (0x0400, 0x04FF),  # Cyrillic
    (0x1E00, 0x1EFF),  # Latin Extended Additional (Vietnamese)
    (0x2000, 0x27BF),  # punctuation, currency, letterlike, arrows, math, box, shapes, symbols
)


def keep(code: int) -> bool:
    return any(lo <= code <= hi for lo, hi in KEEP_RANGES)
DATA_DIR = Path(__file__).resolve().parent.parent / "src/homely/render/fonts/data"


def trim(text: str) -> tuple[str, int, int]:
    out: list[str] = []
    kept = 0
    total = 0
    i = 0
    lines = text.splitlines()
    while i < len(lines):
        line = lines[i]
        if line.startswith("STARTCHAR"):
            j = i
            while j < len(lines) and not lines[j].startswith("ENDCHAR"):
                j += 1
            block = lines[i : j + 1]
            total += 1
            enc = next((b for b in block if b.startswith("ENCODING")), "ENCODING -1")
            parts = enc.split()
            code = int(parts[1])
            if code == -1 and len(parts) > 2:
                code = int(parts[2])
            if keep(code):
                out.extend(block)
                kept += 1
            i = j + 1
            continue
        out.append(line)
        i += 1
    result = "\n".join(out) + "\n"
    result = re.sub(r"^CHARS \d+$", f"CHARS {kept}", result, count=1, flags=re.M)
    return result, kept, total


def main() -> int:
    for path in sorted(DATA_DIR.glob("*.bdf")):
        original = path.read_text(encoding="latin-1")
        trimmed, kept, total = trim(original)
        if kept != total:
            path.write_text(trimmed, encoding="latin-1")
        print(f"{path.name}: kept {kept}/{total} glyphs, {len(trimmed) // 1024} KiB")
    return 0


if __name__ == "__main__":
    sys.exit(main())
