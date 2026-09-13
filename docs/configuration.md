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
