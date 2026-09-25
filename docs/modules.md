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
colors, and a timezone override. Layouts for every supported size, including a letterbox one for
128x32 -- without it a 128-wide board reuses the 64-wide layout and leaves its outer thirds dark.
That layout reads left to right: the time, then AM/PM over the seconds pressed up against the
last digit the way a desk clock shows them, then the date in its own column.

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
- **Forecast days**: `forecast_days: 0` (the default) picks automatically -- five days on panels
  96 px or wider, three on smaller ones. Set 1-5 to override.
- **Feels-like**: `show_feels_like` adds the apparent temperature under the reading, on every
  layout. It is shown whenever the setting is on, including when it matches the temperature --
  hiding it then (most mild days) made the setting look broken.
- **Long text scrolls.** The condition, the feels-like line and the place name are drawn in the
  largest font they fit whole; when they fit none, they scroll through their space as a marquee
  (with a pause at the start) instead of being clipped. A turn with anything to scroll runs at
  30 fps; one with only still text stays at 1 fps.
- Metric or imperial follows the global location units. The last forecast is cached on disk so a
  reboot shows weather immediately.

Provider interface: `homely.modules.weather.providers.WeatherProvider`. Add a provider by
implementing `fetch(lat, lon, units, timezone) -> Forecast` and registering it in `PROVIDERS`.

## News

Headlines from any RSS or Atom feeds (defaults: BBC World, NPR, Hacker News). Each turn shows a
few headlines (`headlines_per_slot`, 10 seconds each by default via `seconds_per_headline`),
wrapped to fit, with the source name in its color and the item age. Feeds are fetched with
conditional requests (ETag/Last-Modified), one bad feed never blocks the others, and
`mix: interleave` takes turns between sources.

## Maze (idle animation)

Each round picks a random maze size (cells at least `min_cell_px` wide), carves a perfect maze,
and opens an entrance on the left edge and an exit on the right edge at random rows. Cells are
not all the same size: leftover pixels are spread across them so the outer walls always land on
the panel edges, with no unlit margin. The thin red walls are drawn one pixel at a time
(`draw_speed`), then the shortest path is traced in green through the cell centers
(`solve_speed`), held for `pause_s`, and the next maze begins.

## Qix (idle animation)

A bundle of lines whose two endpoints drift and bounce around the panel, leaving a fading trail,
as in the 1981 arcade game. Choose `rainbow`, `single` or `duo` colors, trail length, speed and up
to three independent qixes.

`wander` (default 45) is how far the motion strays from a straight bounce. A plain reflection
keeps the speed along each axis forever, so the heading only ever takes four values and a wide
panel settles into the same up-down, left-right path within seconds; `wander` adds a slow drift
to the heading and scatters each bounce. Set it to 0 for billiard-ball bounces.

## More idle animations

- **Starfield**: fly through a 3D field of stars; nearer stars are brighter and streak, and a
  shooting star crosses now and then. `stars`, `speed`, `trails`, `color_mode`.
- **Pipes**: the 3D screensaver. Shaded square tubes with ball joints grow through a voxel grid
  with random turns, each pipe in its own color, until the round's pipes are done; then it fades
  and starts over. `grid`, `pipes`, `speed`, `turn_chance`, `palette`.
- **Game of Life**: Conway's rules on a wrapping board (or hard edges). Newborn cells flash white
  and settle into the color; dying cells leave a fading ghost. A stalled or empty soup fades out
  and reseeds. `cell_px`, `generations_per_second`, `density`, `color_mode`.
- **Lava lamp**: like the real thing, a lump of lava sits pooled at the bottom centre, and blobs
  peel off it one at a time -- a few seconds apart, and never all at once (at least 40% of them are
  always in the lump). Each rides a convection loop up one side, across the top and down the
  other, slides back along the bottom into the lump, rests there a while and goes round again.
  The loop is paced by distance so the speed stays even, and which side rises varies by round. A
  turn opens with everything in the lump. Palettes: `classic`, `ocean`, `toxic`, `sunset`,
  `ember`, `berry`, `cyber`, `mint`, `gold`, `ice`, or your own three colors.
- **TV static**: analog snow with a rolling bar and scanlines; every few seconds the set flips to a
  channel (color bars, a test card, NO SIGNAL, PLEASE STAND BY) and tears back to snow.
- **Snake**: plays itself with a shortest-path search to the food, refusing moves that would cut
  it off from its own tail, and chasing the tail when there is no safe route. When it finally traps
  itself it flashes and restarts.
- **Growing tree**: a space-colonization tree grows branch by branch into a random canopy shape,
  leafs out, turns autumn colors, sheds its leaves to the ground and starts again as a sapling.
  Leaves are stamps rather than single pixels, which vanish on a real panel: `leaf_size: 0` sizes
  them from the panel (2 px up to 32 tall, 3 up to 64, 4 above), or set 1-4 yourself.
- **Skyline**: a generated city under a sky that follows the sun (same palette and solar math as
  the weather module, for your location). The sun and moon arc across, stars twinkle after dusk,
  windows light up in the evening and go dark toward morning, cars pass on the street. `timelapse`
  runs a whole day during the turn starting from now; `realtime` matches the real sky.

- **Light cycles**: two to four riders race across the arena leaving walls of light. For every
  legal move a rider runs one multi-source breadth-first search from its own would-be head and
  each rival head at once and counts the cells it would reach first -- its territory -- which
  covers both not getting boxed in and not handing the board away. It also refuses moves with no
  exit, hugs walls once it is inside a region it can count to the end, and holds a straight line
  while that costs it no territory. `aggression` (default 45) then spends some of that territory:
  among the moves that cost it little, a rider takes the one that closes on a rival instead of the
  one that banks the most space. Scoring on (my territory minus the rival's) cannot do this --
  the search splits the free space between the heads, so that difference ranks the moves in exactly
  the same order as my own share. When nothing is within reach to tell the moves apart the search
  is skipped altogether, which is what used to make three and four riders lag at the start of a
  round. A crash derezzes the trail into flickering fragments, and the last rider standing flashes
  as the winner. `cycles`, `speed`, `lookahead`, `aggression`, `cell_px`, `palette` (classic blue
  vs orange). Cells default to 1-4 px so the arena stays around 1200 cells: small enough for a
  rider to search the whole board before committing, and fat enough that trails read as lines.

All of them are seeded so their goldens are reproducible, and all render in well under a
millisecond per frame on the Mac (the 3D ones draw incrementally into a depth buffer; light
cycles peaks around 2 ms on a step where every rider re-searches the board).

Every animation restarts when the rotation flips to it, rather than resuming where its last turn
left off -- a module implements this by overriding `on_enter()`. Modules whose whole output comes
from the clock or from polled data (clock, weather) have nothing to restart and leave it alone.

## Idle module

The animations always have something to show, so they work well as the **idle module**:
set `rotation.idle_module` to an instance id (for example `maze`) and it is shown whenever every
other module declines to display (no data yet, nothing scheduled). The idle module is skipped in
the normal rotation. Or just leave them in the rotation as regular turns.
