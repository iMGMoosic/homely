# Modules

| Module | Tier | Status | Data source |
|---|---|---|---|
| Clock | Need | available | local time |
| Weather | Need | available | Open-Meteo (no key), pluggable providers |
| News | Need | available | RSS/Atom feeds |
| Maze (idle animation) | Need | available | none |
| Qix (idle animation) | Need | available | none |
| Sports scores | Want | planned | MLB Stats API, then NFL/NHL/NBA |
| Transit | Want | planned | Metro Transit NexTrip (Minneapolis/St. Paul), then GTFS-RT |
| Calendar | Want | planned | ICS URL |
| Arcade game | Looks cool | planned | USB controller |
| Stocks | Looks cool | planned | Finnhub |
| Spotify | Looks cool | planned | Spotify Web API (your own client id) |

Want to write one? See [CONTRIBUTING.md](../CONTRIBUTING.md).

## Text style

Everything on the display is drawn as a **14-segment display** by default (`display.font:
segment`): letters, numbers and punctuation are built from the seven outer bars plus the six inner
strokes of an alphanumeric LED display, rasterized pixel-exact at each size. Lowercase shows as
uppercase, like a real display. Set `display.font: pixel` for classic bitmap fonts instead. Module
code asks for fonts by their pixel-font name and the theme substitutes the matching segment size;
`pixel:<name>` forces a bitmap font for one element.

## Clock

Seven-segment digits by default (`style: segment`) with optional faint "unlit" segments, or a
pixel font (`style: pixel`). 12/24 hour, seconds, blinking colon, date formats, per-element
colors, and a timezone override. Layouts for every supported size.

## Weather

Data from [Open-Meteo](https://open-meteo.com) (free, no API key, non-commercial use, data
CC BY 4.0). Set your location under **Display → Location**; the "Find a place" search fills in
latitude, longitude, name and timezone.

The screen splits in two (left/right on wide panels, top/bottom on tall ones):

- **Temperature half**: a gradient from today's high (top) to today's low (bottom) on a 38-stop
  temperature palette (pale ice blue, deep blue, teal, sand, red, maroon). The current temperature
  sits on it in its own temperature color with a white outline, and `H:` / `L:` at the bottom.
- **Sky half**: takes the color of the sky right now, computed from real sun times for your
  location (astronomical dawn and dusk, sunrise, solar noon, sunset): deep navy at night, warm
  orange around sunrise and sunset, light blue at midday, blended smoothly in between. The
  condition icon (sun, moon, clouds, rain, snow, storm, fog, hail; drawn procedurally so they
  stay crisp at any size) is centered on it with the condition name beneath.
- `view: both` adds a daily-forecast page with hourly rain-chance bars; `forecast` shows only that.
- Metric or imperial follows the global location units. The last forecast is cached on disk so a
  reboot shows weather immediately. Tiny 32x32 panels use a compact single-panel layout.

Provider interface: `homely.modules.weather.providers.WeatherProvider`. Add a provider by
implementing `fetch(lat, lon, units, timezone) -> Forecast` and registering it in `PROVIDERS`.

## News

Headlines from any RSS or Atom feeds (defaults: BBC World, NPR, Hacker News). Each turn shows a
few headlines (`headlines_per_slot`, `seconds_per_headline`), wrapped to fit, with the source name
in its color and the item age. Feeds are fetched with conditional requests (ETag/Last-Modified),
one bad feed never blocks the others, and `mix: interleave` takes turns between sources.

## Maze (idle animation)

Each round picks a random maze size (cells at least `min_cell_px` wide), carves a perfect maze,
and opens an entrance on the left edge and an exit on the right edge at random rows. The thin
red walls are drawn one pixel at a time (`draw_speed`), then the shortest path is traced in
green through the cell centers (`solve_speed`), held for `pause_s`, and the next maze begins.

## Qix (idle animation)

A single jittery line whose endpoints bounce around the panel, moving a random distance each
frame (`jitter`), with a color that wanders one channel at a time (`color_mode: walk`) and a
short fading trail (`trail`, default 5 lines). Rainbow and single-color modes and up to three
qixes are available.

## Idle module

Both animations always have something to show, so they work well as the **idle module**:
set `rotation.idle_module` to an instance id (for example `maze`) and it is shown whenever every
other module declines to display (no data yet, nothing scheduled). The idle module is skipped in
the normal rotation. Or just leave them in the rotation as regular turns.
