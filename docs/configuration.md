# Configuration

Everything is in `/etc/homely/config.yaml` (YAML), owned by the `homely` user. The web UI is the
primary editor and rewrites the file on save, so comments do not survive. Secrets (API keys, the web
password hash) live next to it in `secrets.yaml` with mode 0600.

Resolution order: `--config` flag, `$HOMELY_CONFIG`, `/etc/homely/config.yaml`, then
`~/.config/homely/config.yaml`. State (caches, backups) goes to `$HOMELY_STATE_DIR`, `/var/lib/homely`,
or `~/.local/state/homely`.

## Sections

| Key | Purpose | Applies |
|---|---|---|
| `panel` | rows/cols/chain, hardware mapping, slowdown, PWM, orientation, gamma. Mirrors the driver's options. | restart |
| `display` | `backend` (auto/rgbmatrix/none), `preview`, `emulated_size` for development | restart |
| `web` | host, port, `auth_enabled` | restart |
| `location` | latitude/longitude, timezone, units | live |
| `rotation` | default dwell, transition, target fps, `idle_module` | live |
| `brightness` | level and night schedule | live |
| `modules` | ordered list of `{instance_id, module, enabled, duration_s, settings}` | live |

## Transitions

`rotation.transition` picks how one module gives way to the next, over
`rotation.transition_duration_s`:

| Name | What it does |
|---|---|
| `cut` | no transition (also what any transition does at duration 0) |
| `fade` | cross-fade |
| `fade_black` | dips to black halfway, then comes back up on the new module |
| `slide_left` / `slide_right` / `slide_up` / `slide_down` | the new frame pushes the old one off |
| `wipe_left` / `wipe_right` / `wipe_up` / `wipe_down` | a hard edge sweeps across, uncovering the new frame |
| `curtain_h` / `curtain_v` | the new frame opens out from the middle |
| `blinds` | venetian blinds: bands widen until the new frame covers everything |
| `iris` | a circle opens from the centre |
| `dissolve` | pixels swap over in a fixed random order |
| `pixelate` | the old frame coarsens into fat pixels, the new one resolves out of them |
| `glitch` | rows tear sideways and the two frames interleave |
| `random` | a different one of the above every changeover |

## CLI helpers

```bash
homely config show
homely config validate
homely config set panel.gpio_slowdown 3
homely config set rotation.transition slide_left
homely config set-password
```

Hand edits are picked up with `curl -X POST localhost:8080/api/system/actions/reload-config`
or a service restart.

## Custom fonts

Drop `.bdf` files into `/etc/homely/fonts/`; modules can reference them by file stem.

## Editing the file by hand

You can edit the YAML over SSH while homely is running. The file is checked every couple of
seconds; when it changes, only the sections that differ are applied live (brightness, rotation,
location, modules). Panel, display and web changes still need a restart, and the System page says
so. An invalid file is logged and ignored until it is fixed.
