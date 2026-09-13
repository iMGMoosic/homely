"""Privileged system actions (reboot/shutdown) via a narrowly scoped sudoers entry."""

from __future__ import annotations

import asyncio
import shutil

from homely.system.info import is_root


async def _run(cmd: list[str]) -> tuple[bool, str]:
    if not is_root() and shutil.which("sudo"):
        cmd = ["sudo", "-n", *cmd]
    try:
        proc = await asyncio.create_subprocess_exec(
            *cmd, stdout=asyncio.subprocess.PIPE, stderr=asyncio.subprocess.STDOUT
        )
        out, _ = await asyncio.wait_for(proc.communicate(), timeout=15)
    except (OSError, TimeoutError) as exc:
        return False, str(exc)
    text = out.decode(errors="replace").strip()
    return proc.returncode == 0, text or ("ok" if proc.returncode == 0 else f"exit {proc.returncode}")


async def reboot() -> tuple[bool, str]:
    if not shutil.which("systemctl"):
        return False, "systemctl not available on this system"
    return await _run(["systemctl", "reboot"])


async def shutdown() -> tuple[bool, str]:
    if not shutil.which("systemctl"):
        return False, "systemctl not available on this system"
    return await _run(["systemctl", "poweroff"])
