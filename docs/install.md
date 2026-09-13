# Installing on the Pi

## One-liner

```bash
curl -fsSL https://raw.githubusercontent.com/imgmoosic/homely/main/install.sh | sudo bash
```

What it does (idempotent; re-run it to upgrade):

1. Installs build tools and Python.
2. Creates a `homely` system user and `/etc/homely`, `/var/lib/homely`, `/opt/homely`.
3. Builds the [rpi-rgb-led-matrix](https://github.com/hzeller/rpi-rgb-led-matrix) Python binding into
   `/opt/homely/venv` (3-6 minutes on a Pi 4).
4. Installs the latest `homely-display` release wheel.
5. Writes `/etc/homely/config.yaml` (asks for panel size and the PWM jumper).
6. Installs and enables the `homely` systemd service, an Avahi entry (`http://homely.local:8080`),
   and a sudoers rule for reboot/shutdown from the UI.
7. Disables onboard audio and offers to reserve CPU core 3 for the display.

Options: `--yes`, `--version X.Y.Z`, `--from-pypi`, `--no-isolcpus`, `--no-hostname`, `--rebuild-matrix`,
`--uninstall [--purge]`.

## Manual steps

```bash
sudo apt install git build-essential cmake python3-venv python3-dev cython3
sudo python3 -m venv /opt/homely/venv
sudo /opt/homely/venv/bin/pip install "git+https://github.com/hzeller/rpi-rgb-led-matrix"
sudo /opt/homely/venv/bin/pip install homely-display
sudo /opt/homely/venv/bin/homely config init --config /etc/homely/config.yaml
sudo cp packaging/homely.service /etc/systemd/system/ && sudo systemctl enable --now homely
```

## Day-to-day

```bash
journalctl -u homely -f                       # logs
sudo /opt/homely/venv/bin/homely doctor       # health check
sudo systemctl restart homely
```
