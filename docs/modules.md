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

## Clock

Seven-segment LCD-style digits by default (`style: segment`) with optional faint "unlit" segments,
or a pixel font (`style: pixel`). 12/24 hour, seconds, blinking colon, date formats, per-element
colors, and a timezone override. Layouts for every supported size.

## Weather

Data from [Open-Meteo](https://open-meteo.com) (free, no API key, non-commercial use, data
CC BY 4.0). Set your location under **Display → Location**; the "Find a place" search fills in
latitude, longitude, name and timezone.

- **Icons** are drawn procedurally in a bold, friendly style (sun, moon, clouds, rain, snow, storm,
  fog, hail) so they stay crisp at any panel size.
- **Background gradient**: the top of the panel is colored by today's high temperature and the
  bottom by today's low (purple/blue = cold, yellow/orange/red = hot). `background_brightness`
  keeps it subtle behind the text.
- **Sky strip**: a two-pixel strip on the right edge shows the sky color over the whole day (dark
  blue → yellow at sunrise → sky blue → yellow at sunset → dark blue) with a white marker at the
  current time. It uses the real sunrise/sunset for your location.
- **Views**: `both` shows current conditions for the first half of the turn, then the daily
  forecast (with hourly rain-chance bars where there is room). Or pick one.
- Metric or imperial follows the global location units. The last forecast is cached on disk so a
  reboot shows weather immediately.

Provider interface: `homely.modules.weather.providers.WeatherProvider`. Add a provider by
implementing `fetch(lat, lon, units, timezone) -> Forecast` and registering it in `PROVIDERS`.

## News

Headlines from any RSS or Atom feeds (defaults: BBC World, NPR, Hacker News). Each turn shows a
few headlines (`headlines_per_slot`, `seconds_per_headline`), wrapped to fit, with the source name
in its color and the item age. Feeds are fetched with conditional requests (ETag/Last-Modified),
one bad feed never blocks the others, and `mix: interleave` takes turns between sources.

## Maze (idle animation)

A maze grows from the top-left corner (recursive backtracker), then a little solver walks it
depth-first, backtracking out of dead ends (shown dim) until it reaches the red goal. The solved
path lights up, the screen fades, and a new maze begins. `corridor` picks fine (1 px) or chunky
(3 px) corridors; `build_speed` / `solve_speed` control the pace; `rainbow_walls` colors the walls
by build order. Deterministic under test via a seed.

## Qix (idle animation)

A bundle of lines whose two endpoints drift and bounce around the panel, leaving a fading trail,
as in the 1981 arcade game. Choose `rainbow`, `single` or `duo` colors, trail length, speed and up
to three independent qixes.

## Idle module

Both animations always have something to show, so they work well as the **idle module**:
set `rotation.idle_module` to an instance id (for example `maze`) and it is shown whenever every
other module declines to display (no data yet, nothing scheduled). The idle module is skipped in
the normal rotation. Or just leave them in the rotation as regular turns.
