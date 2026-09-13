"""System facts for the UI and `homely doctor`."""

from __future__ import annotations

import os
import platform
import socket
import sys
from pathlib import Path


def hostname() -> str:
    return socket.gethostname()


def ip_addresses() -> list[str]:
    ips: list[str] = []
    try:
        for family, target in ((socket.AF_INET, ("10.255.255.255", 1)), (socket.AF_INET6, ("2001:db8::1", 1))):
            s = socket.socket(family, socket.SOCK_DGRAM)
            try:
                s.connect(target)
                ip = s.getsockname()[0]
                if ip and not ip.startswith(("127.", "::1")):
                    ips.append(ip)
            except OSError:
                pass
            finally:
                s.close()
    except OSError:
        pass
    return ips


def cpu_temp_c() -> float | None:
    p = Path("/sys/class/thermal/thermal_zone0/temp")
    try:
        return int(p.read_text().strip()) / 1000.0
    except (OSError, ValueError):
        return None


def python_version() -> str:
    return sys.version.split()[0]


def platform_string() -> str:
    model = Path("/proc/device-tree/model")
    try:
        text = model.read_bytes().decode("utf-8", "ignore").strip("\x00 ")
        if text:
            return text
    except OSError:
        pass
    return f"{platform.system()} {platform.machine()}"


def is_root() -> bool:
    return hasattr(os, "geteuid") and os.geteuid() == 0
