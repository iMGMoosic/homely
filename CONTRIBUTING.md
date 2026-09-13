# Contributing to homely

Thanks for helping. This guide covers the dev setup and, most importantly, how to add a module.

## Dev setup (macOS or Linux, no hardware needed)

```bash
git clone https://github.com/imgmoosic/homely && cd homely
make setup      # Python venv (via uv) + npm install + dev config
make dev        # API on :8080, Vite with hot reload on :5173
```

Open http://localhost:5173. The live preview on the dashboard is the emulator: whatever
the Pi would show, you see there. `make check` runs ruff, mypy, pytest, and the frontend checks.

Useful commands:

```bash
.venv/bin/homely render --module clock --size 64x32 --scale 6 --out clock.png   # one frame to a PNG
.venv/bin/homely render --module clock --settings '{"time_format":"24h"}'
.venv/bin/python -m pytest --update-golden                                        # accept new golden images
```

## Project layout

```
src/homely/core      module API, registry, scheduler (rotation), render loop
src/homely/render    Canvas, fonts (BDF), text helpers, per-size layout registry
src/homely/display   display backends: rgbmatrix (hardware), web preview, test displays
src/homely/config    YAML config, secrets, migrations
src/homely/data      HTTP client, pollers, DataSlot, location
src/homely/web       FastAPI app + websockets
src/homely/modules   one directory per module
web/                 Svelte frontend
tests/               pytest; tests/golden holds reference PNGs
```

## Adding a module

1. Copy `src/homely/modules/_template` to `src/homely/modules/<id>/` and rename the classes.
2. Fill in `ModuleInfo` in `module.py`. `id` must be unique and lowercase.
3. Declare settings in `settings.py` as a pydantic model. The web UI renders a form from
   it automatically. Supported field shapes:
   - `str`, `int`, `float`, `bool`, `Literal[...]`, `str | None`
   - `list[str]` (rendered as an add/remove list)
   - `SecretStr` for API keys (stored in `secrets.yaml`, masked in the UI)
   - nested pydantic models (rendered as a fieldset)

   UI hints via `json_schema_extra`: `{"format": "color"}` for `#RRGGBB` colors,
   `"x-widget": "slider" | "textarea" | "time" | "timezone" | "hidden"`,
   `"x-group": "Appearance"`, `"x-order": 10`, `"x-unit": "px"`, `"x-placeholder"`, `"x-help"`.
4. Fetch data in `setup()` with `self.ctx.poll("name", timedelta(minutes=15), self._fetch)`.
   Store results in a `DataSlot` or by replacing an immutable object. **Never do I/O in
   `render()`**; it runs on the render thread 30 times a second.
5. Return `False` from `should_display()` when you have nothing to show; the rotation skips you.
6. Add `@layout(64, 64)` renderers for the sizes you design for, plus a `@layout_fallback`
   that works anywhere. A smaller exact layout is reused (centered or integer-upscaled) on
   bigger panels automatically.
7. Use `self.ctx.now()` for time (never `datetime.now()`; ruff enforces this) so renders are testable.
8. Register the class in `src/homely/modules/__init__.py`.
9. Add golden tests in `tests/modules/test_<id>.py` (see `test_clock.py`), run
   `pytest --update-golden` once, and check the PNGs under `tests/golden/<id>/` look right.

Static modules (`default_fps=0`) render once per rotation slot; call `self.ctx.invalidate()`
when new data arrives. Animated modules set `default_fps` to 30 (or 60) and get `frame.dt`.

## Third-party modules

A separate package can register modules with an entry point:

```toml
[project.entry-points."homely.modules"]
mymodule = "my_package.module:MyModule"
```

## Style

- Python: ruff (lint + format, line length 120), mypy strict. `make fmt` fixes most things.
- Svelte: prettier. Svelte 5 runes (`$state`, `$derived`, `$props`).
- Small PRs with a screenshot or PNG of the module at 64x64 are the easiest to review.

## Releasing

Bump `version` in `pyproject.toml`, tag `vX.Y.Z`, push the tag. CI builds the frontend,
attaches the wheel and `install.sh` to a GitHub Release, and (if enabled) publishes to PyPI.
