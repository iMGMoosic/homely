# Modules

| Module | Tier | Status | Data source |
|---|---|---|---|
| Clock | Need | available | local time |
| Weather | Need | available | Open-Meteo (no key), pluggable providers |
| News | Need | available | RSS/Atom feeds |
| Maze (idle animation) | Need | available | none |
| Qix (idle animation) | Need | available | none |
| Starfield, Pipes (3D idle animations) | Need | available | none |
| Game of Life, Lava lamp, TV static (idle animations) | Need | available | none |
| Snake, Growing tree (idle animations) | Need | available | none |
| Skyline (day/night idle animation) | Need | available | sun times for your location |
| Light cycles (idle animation) | Need | available | none |
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
  bottom by today's low, on a 38-stop palette (pale ice blue, deep blue, teal, sand, red, maroon).
  `background_brightness` keeps it subtle behind the text.
- **Sky strip**: a two-pixel strip on the right edge shows the sky over the whole day, top to
  bottom, with a white marker at the current time. Each row is the two-tone sky of that moment
  (navy at night, warm orange through dawn and dusk, light blue at midday), computed from real sun
  times for your location: astronomical dawn and dusk, sunrise, solar noon and sunset.
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

Each round picks a random maze size (cells at least `min_cell_px` wide), carves a perfect maze,
and opens an entrance on the left edge and an exit on the right edge at random rows. The thin
red walls are drawn one pixel at a time (`draw_speed`), then the shortest path is traced in
green through the cell centers (`solve_speed`), held for `pause_s`, and the next maze begins.

## Qix (idle animation)

A bundle of lines whose two endpoints drift and bounce around the panel, leaving a fading trail,
as in the 1981 arcade game. Choose `rainbow`, `single` or `duo` colors, trail length, speed and up
to three independent qixes.

## More idle animations

- **Starfield**: fly through a 3D field of stars; nearer stars are brighter and streak, and a
  shooting star crosses now and then. `stars`, `speed`, `trails`, `color_mode`.
- **Pipes**: the 3D screensaver. Shaded square tubes with ball joints grow through a voxel grid
  with random turns, each pipe in its own color, until the round's pipes are done; then it fades
  and starts over. `grid`, `pipes`, `speed`, `turn_chance`, `palette`.
- **Game of Life**: Conway's rules on a wrapping board (or hard edges). Newborn cells flash white
  and settle into the color; dying cells leave a fading ghost. A stalled or empty soup fades out
  and reseeds. `cell_px`, `generations_per_second`, `density`, `color_mode`.
- **Lava lamp**: slow metaball blobs that rise, sink and merge; `classic`, `ocean`, `toxic`,
  `sunset` palettes or your own three colors.
- **TV static**: analog snow with a rolling bar and scanlines; every few seconds the set flips to a
  channel (color bars, a test card, NO SIGNAL, PLEASE STAND BY) and tears back to snow.
- **Snake**: plays itself with a shortest-path search to the food, refusing moves that would cut
  it off from its own tail, and chasing the tail when there is no safe route. When it finally traps
  itself it flashes and restarts.
- **Growing tree**: a space-colonization tree grows branch by branch into a random canopy shape,
  leafs out, turns autumn colors, sheds its leaves to the ground and starts again as a sapling.
- **Skyline**: a generated city under a sky that follows the sun (same palette and solar math as
  the weather module, for your location). The sun and moon arc across, stars twinkle after dusk,
  windows light up in the evening and go dark toward morning, cars pass on the street. `timelapse`
  runs a whole day during the turn starting from now; `realtime` matches the real sky.

- **Light cycles**: two to four riders race across the arena leaving walls of light. Each steers
  by how much open room a move leaves (a bounded flood fill) and swerves late when a wall is
  close; a crash derezzes the trail into flickering fragments, and the last rider standing
  flashes as the winner. `cycles`, `speed`, `lookahead`, `palette` (classic blue vs orange).

All of them are seeded so their goldens are reproducible, and all render in well under a
millisecond per frame on the Mac (the 3D ones draw incrementally into a depth buffer).

## Idle module

The animations always have something to show, so they work well as the **idle module**:
set `rotation.idle_module` to an instance id (for example `maze`) and it is shown whenever every
other module declines to display (no data yet, nothing scheduled). The idle module is skipped in
the normal rotation. Or just leave them in the rotation as regular turns.
