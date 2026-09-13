# Development

See [CONTRIBUTING.md](../CONTRIBUTING.md) for the module-writing guide. This page has the extra bits.

## Architecture in one paragraph

One process. The asyncio main thread runs the FastAPI server and every module's data pollers. A single
render thread runs a fixed-tick loop: the `Scheduler` picks the current module, asks it to `render()` into
a Pillow canvas (static modules once per slot, animated ones at their fps), applies a transition, and
pushes the frame to the `Display`. On the Pi the display is the hzeller matrix plus the web preview; on a
laptop it is the web preview alone. Config changes flow through an in-process event bus, so saving in the
UI takes effect within a frame.

## Emulating other panel sizes

Set `display.emulated_size: 128x32` (or any supported size) in `dev/config.yaml`, or run
`homely render --size 32x64`.

## Frontend

`web/` is Svelte 5 + Vite + TypeScript. `npm run dev` proxies `/api` to the Python server on 8080.
`npm run build` writes to `src/homely/web/static`, which the wheel embeds. The settings form is generated
from each module's JSON Schema in `web/src/lib/form/`.

## Tests

`pytest` runs everything without hardware. Rendering tests compare against PNGs in `tests/golden/`;
`pytest --update-golden` accepts changes, and on failure a side-by-side diff is written to
`tests/.golden_out/`.
