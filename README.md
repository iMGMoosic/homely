# homely

A Tidbyt-like LED matrix display for Raspberry Pi. Plug a HUB75 RGB LED panel into a Pi 4
with an Adafruit RGB Matrix Bonnet, run one install command, and configure everything from
your phone: clock, weather, news, transit times, sports scores, idle animations and more.

> **Status: early development.** The core runtime, web UI, installer and the Clock, Weather and
> News modules and the Maze/Qix idle animations work. Sports, transit and calendar are next. See
> [docs/modules.md](docs/modules.md).

## How it works

- Modules take turns on the panel, Tidbyt style: each enabled module gets the full screen for a
  configurable number of seconds, then the next one fades in.
- A web app served by the Pi lets you enable, reorder and configure modules, set brightness and a
  night schedule, and see a **live preview** of the panel from any device on your network.
- Everything is designed for 64x64 first. 32x32, 64x32, 128x32, 128x64 and 128x128 (plus portrait)
  are supported by the layout system; each module grows dedicated layouts over time.
- Runs on a Mac or Linux laptop without hardware. The live preview is the emulator.

## Hardware

- Raspberry Pi 4 (Raspberry Pi OS Bookworm, 64-bit Lite recommended)
- Adafruit RGB Matrix Bonnet (bridge the "E" pad to "8" for 64x64 panels)
- A HUB75 RGB LED panel, e.g. 64x64 P2
- A separate 5 V power supply for the panel (4 A or more for a 64x64)

Details, tuning and troubleshooting: [docs/hardware.md](docs/hardware.md).

## Install (on the Pi)

```bash
curl -fsSL https://raw.githubusercontent.com/imgmoosic/homely/main/install.sh | sudo bash
```

The installer builds the LED driver, installs homely as a systemd service, disables onboard audio
(it conflicts with the panel's PWM), and prints the URL. Then open `http://homely.local:8080`
(or `http://<pi-ip>:8080`). Re-run the same command to upgrade. See [docs/install.md](docs/install.md).

## Modules

| Module | Status |
|---|---|
| Clock (seven-segment LCD look or pixel font) | available |
| Weather (Open-Meteo, no API key; temperature gradient, sky strip, friendly icons) | available |
| News (RSS/Atom feeds) | available |
| Idle animations: maze builder/solver, Qix | available |
| Sports scores (MLB, NFL, NHL, NBA) | planned |
| Transit (Metro Transit MSP, then GTFS-RT) | planned |
| Calendar (ICS URL) | planned |
| Arcade game with a USB controller, Stocks, Spotify | later |

Writing a module is a couple of files; see [CONTRIBUTING.md](CONTRIBUTING.md).

## Development (any machine, no hardware needed)

```bash
make setup      # Python 3.11 venv via uv, npm install, dev config
make dev        # API on :8080 and Vite on :5173
```

Open http://localhost:5173. Other handy commands:

```bash
.venv/bin/homely render --module clock --size 64x32 --scale 6 --out clock.png
.venv/bin/homely preview        # emulator + web UI from the built bundle
make check                      # ruff, mypy, pytest
```

## License

MIT. The LED matrix driver, [hzeller/rpi-rgb-led-matrix](https://github.com/hzeller/rpi-rgb-led-matrix),
is GPL-2.0-or-later and is installed separately on the Pi by `install.sh`; homely never bundles it.
Bundled bitmap fonts are public domain (X11 misc-fixed) and MIT (tom-thumb); see
`src/homely/render/fonts/data/LICENSE`.
