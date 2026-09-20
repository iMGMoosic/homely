#!/usr/bin/env bash
# homely installer for Raspberry Pi OS (Bookworm, 64-bit).
#   curl -qfsSL https://raw.githubusercontent.com/imgmoosic/homely/main/install.sh | sudo bash
# Options (append after "bash -s --"):
#   --version X.Y.Z   install a specific release (default: latest)
#   --from-pypi       install homely-display from PyPI instead of a GitHub release wheel
#   --from-source     build and install straight from the git repo (no release needed)
#   --yes             non-interactive (accept defaults, no isolcpus prompt)
#   --no-isolcpus     don't add the CPU isolation kernel parameter
#   --no-hostname     don't set the hostname to "homely"
#   --rebuild-matrix  rebuild the rgbmatrix Python binding even if it imports
#   --uninstall       remove the service and /opt/homely (add --purge to also remove config/state)
set -euo pipefail

REPO="imgmoosic/homely"
MATRIX_REPO="https://github.com/hzeller/rpi-rgb-led-matrix"
MATRIX_REF="51d3231e370593b60952b2c3b18d2e3802329f18"   # pinned hzeller commit (2026-09-07T18:36:32Z)
PREFIX=/opt/homely
VENV="$PREFIX/venv"
CONF_DIR=/etc/homely
STATE_DIR=/var/lib/homely
USER_NAME=homely

VERSION=""; FROM_PYPI=0; FROM_SOURCE=0; YES=0; ISOLCPUS=1; SET_HOSTNAME=1; REBUILD=0; UNINSTALL=0; PURGE=0
REF=main

# Strip whitespace and control characters; a stray space or CR (easy to introduce by copying a
# command out of a rendered page) otherwise reaches curl as "URL rejected: Malformed input".
clean() { printf '%s' "${1:-}" | tr -d '[:space:]'; }
while [ $# -gt 0 ]; do
  case "$1" in
    --version) VERSION=$(clean "${2:-}"); shift ;;
    --from-pypi) FROM_PYPI=1 ;;
    --from-source) FROM_SOURCE=1 ;;
    --ref) REF=$(clean "${2:-}"); shift ;;
    --yes|-y) YES=1 ;;
    --no-isolcpus) ISOLCPUS=0 ;;
    --no-hostname) SET_HOSTNAME=0 ;;
    --rebuild-matrix) REBUILD=1 ;;
    --uninstall) UNINSTALL=1 ;;
    --purge) PURGE=1 ;;
    *) echo "unknown option: $1" >&2; exit 2 ;;
  esac
  shift
done

log()  { printf '\033[1;36m==>\033[0m %s\n' "$*"; }
warn() { printf '\033[1;33mwarning:\033[0m %s\n' "$*" >&2; }
die()  { printf '\033[1;31merror:\033[0m %s\n' "$*" >&2; exit 1; }
ask()  { # ask "question" default(y/n)
  if [ "$YES" = 1 ]; then [ "$2" = y ]; return; fi
  local reply; read -r -p "$1 [$2] " reply </dev/tty || reply=""
  reply="${reply:-$2}"; [[ "$reply" =~ ^[Yy] ]]
}

[ "$(id -u)" = 0 ] || die "run as root: curl ... | sudo bash"

# ---------- curl sanity ----------
# curl reads ~/.curlrc (and $CURL_HOME/.curlrc) before every request. A malformed entry there --
# or a bad proxy variable -- makes every single fetch fail with a confusing error that names no
# URL, so check once, up front, and say exactly what is wrong.
# -q must come first: it stops curl from reading ~/.curlrc. A stray "url =" line there adds a
# second, bogus request to every invocation, which swallows -o (so downloads land on stdout and
# the file is never written) and prints "URL rejected: Malformed input to a URL function".
fetch() { # fetch URL [curl args...]
  local url="$1"; shift
  case "$url" in
    *[[:space:]]*) die "internal: URL contains whitespace: '$url'" ;;
  esac
  curl -q -fsSL "$url" "$@"
}

check_curl() {
  local out rc
  out=$(curl -q -fsS -o /dev/null -w '%{http_code}' https://api.github.com/ 2>&1); rc=$?
  if [ "$rc" != 0 ]; then
    warn "curl cannot reach api.github.com (exit $rc): $out"
    case "$rc" in
      5) die "curl cannot use the configured proxy: https_proxy=${https_proxy:-unset} http_proxy=${http_proxy:-unset}" ;;
      6|7|28) die "no network access to api.github.com from this Pi." ;;
      *) die "fix curl first, then re-run (try: curl -v https://api.github.com/)." ;;
    esac
  fi
  # curl works; warn about a broken curlrc anyway, since anything else the user runs will trip on it.
  for f in "${CURL_HOME:+$CURL_HOME/.curlrc}" "$HOME/.curlrc" /root/.curlrc; do
    [ -n "$f" ] && [ -f "$f" ] || continue
    if ! curl -fsS https://api.github.com/ >/dev/null 2>&1; then
      warn "$f contains an entry that breaks plain curl commands (homely itself is unaffected; it uses curl -q):"
      sed -n '1,20p' "$f" >&2
    fi
    break
  done
}
check_curl

if [ "$UNINSTALL" = 1 ]; then
  log "Stopping and removing the homely service"
  systemctl disable --now homely 2>/dev/null || true
  rm -f /etc/systemd/system/homely.service /etc/avahi/services/homely.service /etc/sudoers.d/homely
  systemctl daemon-reload
  rm -rf "$PREFIX"
  if [ "$PURGE" = 1 ]; then rm -rf "$CONF_DIR" "$STATE_DIR"; userdel "$USER_NAME" 2>/dev/null || true; fi
  log "Removed. Boot config edits (audio off, isolcpus) were left in place; they are harmless."
  exit 0
fi

# ---------- preflight ----------
ARCH=$(uname -m)
[ "$ARCH" = aarch64 ] || warn "expected aarch64, got $ARCH; continuing anyway"
. /etc/os-release 2>/dev/null || true
case "${VERSION_CODENAME:-}" in
  bookworm|trixie) : ;;
  *) warn "tested on Raspberry Pi OS Bookworm and Trixie; you have ${PRETTY_NAME:-unknown}" ;;
esac
if [ -r /proc/device-tree/model ]; then log "Detected: $(tr -d '\0' </proc/device-tree/model)"; fi
BOOT=/boot/firmware; [ -d "$BOOT" ] || BOOT=/boot

# ---------- packages ----------
log "Installing system packages"
apt-get update -qq
DEBIAN_FRONTEND=noninteractive apt-get install -y -qq --no-install-recommends \
  git build-essential cmake python3 python3-venv python3-dev python3-pip cython3 avahi-daemon curl ca-certificates

# ---------- user & dirs ----------
if ! id "$USER_NAME" >/dev/null 2>&1; then
  log "Creating system user $USER_NAME"
  useradd --system --home-dir "$STATE_DIR" --shell /usr/sbin/nologin "$USER_NAME"
fi
for g in gpio video input; do getent group "$g" >/dev/null && usermod -aG "$g" "$USER_NAME" || true; done
mkdir -p "$PREFIX/src" "$CONF_DIR" "$STATE_DIR"
chown -R "$USER_NAME:$USER_NAME" "$CONF_DIR" "$STATE_DIR"
chmod 755 "$CONF_DIR"

# ---------- venv ----------
if [ ! -x "$VENV/bin/python" ]; then
  log "Creating virtualenv at $VENV"
  python3 -m venv "$VENV"
fi
"$VENV/bin/pip" install -q --upgrade pip wheel

# ---------- rgbmatrix binding ----------
if [ "$REBUILD" = 1 ] || ! "$VENV/bin/python" -c "import rgbmatrix" 2>/dev/null; then
  log "Building the rpi-rgb-led-matrix Python binding (3-6 minutes on a Pi 4)"
  SRC="$PREFIX/src/rpi-rgb-led-matrix"
  if [ ! -d "$SRC/.git" ]; then git clone -q "$MATRIX_REPO" "$SRC"; fi
  git -C "$SRC" fetch -q origin
  git -C "$SRC" checkout -q "$MATRIX_REF"
  "$VENV/bin/pip" install -q "$SRC"
  "$VENV/bin/python" -c "import rgbmatrix" || die "rgbmatrix binding failed to import after build"
else
  log "rgbmatrix binding already installed"
fi

# ---------- homely ----------
install_from_source() {
  log "Installing homely from source ($REPO@$REF); this also needs the web UI, which is built in CI"
  "$VENV/bin/pip" install -q --upgrade "git+https://github.com/$REPO@$REF"
}

if [ "$FROM_SOURCE" = 1 ]; then
  install_from_source
elif [ "$FROM_PYPI" = 1 ]; then
  log "Installing homely-display from PyPI"
  if [ -n "$VERSION" ]; then "$VENV/bin/pip" install -q --upgrade "homely-display==$VERSION"; else "$VENV/bin/pip" install -q --upgrade homely-display; fi
else
  API="https://api.github.com/repos/$REPO/releases"
  if [ -z "$VERSION" ]; then
    # `|| true` so a 404 (no releases yet) is reported by us, not as a raw curl error under `set -e`.
    LATEST=$(fetch "$API/latest" || true)
    VERSION=$(printf '%s' "$LATEST" | sed -n 's/.*"tag_name": *"v\{0,1\}\([^"]*\)".*/\1/p' | head -n1)
    VERSION=$(clean "$VERSION")
    if [ -z "$VERSION" ]; then
      warn "$REPO has no published release yet"
      log "Falling back to a source install; pass --version X.Y.Z once releases exist"
      install_from_source
      VERSION=source
    fi
  fi
  if [ "$VERSION" != source ]; then
    log "Installing homely $VERSION from GitHub release"
    WHEEL_URL=$(fetch "$API/tags/v$VERSION" | sed -n 's/.*"browser_download_url": *"\([^"]*\.whl\)".*/\1/p' | head -n1)
    WHEEL_URL=$(clean "$WHEEL_URL")
    [ -n "$WHEEL_URL" ] || die "release v$VERSION has no wheel attached; try --from-source"
    TMP=$(mktemp -d); trap 'rm -rf "$TMP"' EXIT
    fetch "$WHEEL_URL" -o "$TMP/homely.whl"
    "$VENV/bin/pip" install -q --upgrade "$TMP/homely.whl"
  fi
fi
"$VENV/bin/homely" version

# ---------- config ----------
if [ ! -f "$CONF_DIR/config.yaml" ]; then
  log "Writing default config to $CONF_DIR/config.yaml"
  ROWS=64; COLS=64; MAPPING=adafruit-hat
  if [ "$YES" != 1 ]; then
    read -r -p "Panel rows [64]: " r </dev/tty || true; ROWS=${r:-64}
    read -r -p "Panel columns [64]: " c </dev/tty || true; COLS=${c:-64}
    if ask "Did you solder the GPIO4-GPIO18 jumper on the Bonnet (flicker-free PWM)?" n; then MAPPING=adafruit-hat-pwm; fi
  fi
  sudo -u "$USER_NAME" "$VENV/bin/homely" config init --config "$CONF_DIR/config.yaml" --rows "$ROWS" --cols "$COLS" --mapping "$MAPPING"
fi
chown -R "$USER_NAME:$USER_NAME" "$CONF_DIR" "$STATE_DIR"

# ---------- systemd / avahi / sudoers ----------
log "Installing systemd service"
PKG_DIR=$("$VENV/bin/python" -c "import homely, os; print(os.path.dirname(homely.__file__))")
if [ -f "$PKG_DIR/packaging/homely.service" ]; then
  install -m 644 "$PKG_DIR/packaging/homely.service" /etc/systemd/system/homely.service
  install -m 644 "$PKG_DIR/packaging/homely.avahi.xml" /etc/avahi/services/homely.service
  install -m 440 "$PKG_DIR/packaging/homely.sudoers" /etc/sudoers.d/homely
else
  RAW="https://raw.githubusercontent.com/$REPO/$REF/packaging"
  fetch "$RAW/homely.service" -o /etc/systemd/system/homely.service
  fetch "$RAW/homely.avahi.xml" -o /etc/avahi/services/homely.service
  fetch "$RAW/homely.sudoers" -o /etc/sudoers.d/homely; chmod 440 /etc/sudoers.d/homely
fi
visudo -cf /etc/sudoers.d/homely >/dev/null || { rm -f /etc/sudoers.d/homely; warn "sudoers entry invalid; reboot/shutdown from the UI disabled"; }
systemctl daemon-reload
systemctl enable homely >/dev/null

if [ "$SET_HOSTNAME" = 1 ] && [ "$(hostname)" != homely ] && ask "Set the hostname to 'homely' (reach the UI at http://homely.local:8080)?" y; then
  OLD=$(hostname); hostnamectl set-hostname homely
  sed -i "s/\b$OLD\b/homely/g" /etc/hosts
fi

# ---------- boot config ----------
REBOOT=0
CFG="$BOOT/config.txt"
if [ -f "$CFG" ] && ! grep -q '^dtparam=audio=off' "$CFG"; then
  log "Disabling onboard audio (shares PWM hardware with the LED matrix)"
  sed -i 's/^dtparam=audio=on/# dtparam=audio=on  # disabled by homely/' "$CFG"
  printf '\n# homely: onboard audio conflicts with the LED matrix PWM\ndtparam=audio=off\n' >> "$CFG"
  REBOOT=1
fi
if [ ! -f /etc/modprobe.d/homely-blacklist-audio.conf ]; then
  echo 'blacklist snd_bcm2835' > /etc/modprobe.d/homely-blacklist-audio.conf; REBOOT=1
fi
CMD="$BOOT/cmdline.txt"
if [ "$ISOLCPUS" = 1 ] && [ -f "$CMD" ] && ! grep -q isolcpus "$CMD"; then
  if ask "Reserve CPU core 3 for the LED refresh (isolcpus, recommended for a steady image)?" y; then
    sed -i '1 s/$/ isolcpus=domain,managed_irq,3 nohz_full=3 rcu_nocbs=3 irqaffinity=0,1,2/' "$CMD"; REBOOT=1
  fi
fi

# ---------- start ----------
systemctl restart homely
sleep 2
IP=$(hostname -I 2>/dev/null | awk '{print $1}')
echo
log "homely is installed."
echo "    Web UI:   http://$(hostname).local:8080   or   http://${IP:-<pi-ip>}:8080"
echo "    Logs:     journalctl -u homely -f"
echo "    Doctor:   sudo $VENV/bin/homely doctor"
echo "    Upgrade:  re-run this installer"
if [ "$REBOOT" = 1 ]; then
  echo
  warn "Boot configuration changed. Reboot to apply (sudo reboot)."
  if ask "Reboot now?" n; then reboot; fi
fi
