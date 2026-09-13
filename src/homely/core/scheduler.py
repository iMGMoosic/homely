"""Rotation state machine. Runs on the render thread; controlled via a thread-safe queue."""

from __future__ import annotations

import logging
import queue
import traceback
from collections.abc import Callable
from dataclasses import dataclass
from datetime import datetime
from enum import Enum
from typing import Any

from PIL import Image

from homely.core.events import ModuleChanged, ModuleError, TakeoverChanged
from homely.core.input import InputEvent
from homely.core.module import FrameInfo
from homely.core.registry import ModuleInstance
from homely.core.takeover import Takeover, TakeoverStack
from homely.core.transitions import Transition
from homely.render.canvas import Canvas
from homely.render.size import Size

log = logging.getLogger(__name__)

BLANK_RECHECK_S = 5.0
INF = float("inf")


class Phase(str, Enum):
    SHOWING = "showing"
    TRANSITION = "transition"
    BLANK = "blank"
    TAKEOVER = "takeover"


@dataclass
class Slot:
    instance: ModuleInstance
    started_at: float
    duration: float
    fps: int
    last_frame: Image.Image | None = None
    last_render_at: float = 0.0
    frame_index: int = 0
    dirty: bool = True


@dataclass(frozen=True)
class SchedulerState:
    phase: str
    current: str | None
    current_module: str | None
    pinned: str | None
    slot_elapsed: float
    slot_duration: float
    takeover: str | None
    rotation: tuple[str, ...]


class Scheduler:
    def __init__(
        self,
        size: Size,
        *,
        transition: Transition,
        now_fn: Callable[[], datetime],
        default_duration: float,
        on_event: Callable[[Any], None] | None = None,
    ) -> None:
        self.size = size
        self.transition = transition
        self._now = now_fn
        self.default_duration = default_duration
        self._on_event = on_event or (lambda e: None)

        self._rotation: list[ModuleInstance] = []
        self._idle: ModuleInstance | None = None
        self._by_id: dict[str, ModuleInstance] = {}
        self._commands: queue.Queue[tuple[str, Any]] = queue.Queue()
        self._inputs: queue.Queue[InputEvent] = queue.Queue()
        self.takeovers = TakeoverStack()

        self.phase = Phase.BLANK
        self.slot: Slot | None = None
        self._prev_frame: Image.Image | None = None
        self._transition_start = 0.0
        self._pinned: str | None = None
        self._blank_checked_at = -INF
        self._blank_frame = Image.new("RGB", size.as_tuple())
        self._last_output: Image.Image | None = None
        self._canvas = Canvas(size)
        self._last_t = 0.0

    # ---- control from other threads ------------------------------------------------

    def apply_rotation(self, instances: list[ModuleInstance], idle: ModuleInstance | None = None) -> None:
        self._commands.put(("rotation", (list(instances), idle)))

    def next(self) -> None:
        self._commands.put(("next", None))

    def prev(self) -> None:
        self._commands.put(("prev", None))

    def pin(self, instance_id: str | None) -> None:
        self._commands.put(("pin", instance_id))

    def invalidate(self, instance_id: str) -> None:
        self._commands.put(("invalidate", instance_id))

    def request_takeover(self, instance_id: str, priority: int, timeout: float | None) -> None:
        self._commands.put(("takeover", (instance_id, priority, timeout)))

    def release_takeover(self, instance_id: str) -> None:
        self._commands.put(("release", instance_id))

    def push_input(self, event: InputEvent) -> None:
        self._inputs.put(event)

    @property
    def last_output(self) -> Image.Image | None:
        return self._last_output

    def state(self) -> SchedulerState:
        slot = self.slot
        active = self.takeovers.active()
        return SchedulerState(
            phase=self.phase.value,
            current=slot.instance.instance_id if slot else None,
            current_module=slot.instance.module_id if slot else None,
            pinned=self._pinned,
            slot_elapsed=(self._last_t - slot.started_at) if slot else 0.0,
            slot_duration=slot.duration if slot else 0.0,
            takeover=active.instance_id if active else None,
            rotation=tuple(i.instance_id for i in self._rotation),
        )

    # ---- render thread -------------------------------------------------------------

    def tick(self, t: float) -> Image.Image | None:
        """Advance and return the frame to display, or None if the output is unchanged."""
        self._last_t = t
        self._drain_commands(t)
        self.takeovers.expire(t)
        self._reconcile_takeover(t)

        if self.slot is None:
            self._advance(t, None)

        cur = self.slot
        if cur is None:
            return self._blank(t)

        if (
            self.phase is Phase.SHOWING
            and self._pinned != cur.instance.instance_id
            and t - cur.started_at >= cur.duration
        ):
            advanced = self._advance(t, cur.instance)
            if advanced is None:
                return self._blank(t)
            cur = advanced
        slot = cur

        self._deliver_inputs(slot)
        frame = self._render_slot(slot, t)
        if frame is None:  # the module blew up; slot was ended
            return self.tick(t) if self.slot is not None else self._blank(t)

        if self.phase is Phase.TRANSITION and self._prev_frame is not None and self.transition.duration > 0:
            p = (t - self._transition_start) / self.transition.duration
            if p >= 1.0:
                self.phase = Phase.SHOWING
                self._prev_frame = None
                out = frame
            else:
                out = self.transition.blend(self._prev_frame, frame, p)
        else:
            if self.phase is Phase.TRANSITION:
                self.phase = Phase.SHOWING
                self._prev_frame = None
            out = frame

        if out is self._last_output:
            return None
        self._last_output = out
        return out

    # ---- internals -----------------------------------------------------------------

    def _blank(self, t: float) -> Image.Image | None:
        if self.phase is not Phase.BLANK:
            self.phase = Phase.BLANK
            self._on_event(ModuleChanged(instance_id=None, phase=Phase.BLANK.value))
        if self._last_output is self._blank_frame:
            return None
        self._last_output = self._blank_frame
        return self._blank_frame

    def _drain_commands(self, t: float) -> None:
        while True:
            try:
                cmd, arg = self._commands.get_nowait()
            except queue.Empty:
                return
            if cmd == "rotation":
                instances, idle = arg
                self._rotation = instances
                self._idle = idle
                self._by_id = {i.instance_id: i for i in [*instances, *([idle] if idle else [])]}
                if self.slot is not None:
                    cur = self._by_id.get(self.slot.instance.instance_id)
                    if cur is None or not cur.enabled():
                        self._end_slot(t)
                    elif cur is not self.slot.instance:
                        self.slot.instance = cur  # same id, fresh object after settings change
                        self.slot.dirty = True
                if self._pinned and self._pinned not in self._by_id:
                    self._pinned = None
            elif cmd == "next":
                self._advance(t, self.slot.instance if self.slot else None)
            elif cmd == "prev":
                self._advance(t, self.slot.instance if self.slot else None, backwards=True)
            elif cmd == "pin":
                self._pinned = arg
                if arg is not None and (self.slot is None or self.slot.instance.instance_id != arg):
                    inst = self._by_id.get(arg)
                    if inst is not None:
                        self._start_slot(inst, t)
            elif cmd == "invalidate":
                if self.slot is not None and self.slot.instance.instance_id == arg:
                    self.slot.dirty = True
            elif cmd == "takeover":
                instance_id, priority, timeout = arg
                expires = None if timeout is None else t + timeout
                self.takeovers.push(Takeover(instance_id=instance_id, priority=priority, expires_at=expires))
                self._on_event(TakeoverChanged(instance_id=instance_id))
            elif cmd == "release":
                self.takeovers.pop(arg)
                active = self.takeovers.active()
                self._on_event(TakeoverChanged(instance_id=active.instance_id if active else None))

    def _reconcile_takeover(self, t: float) -> None:
        active = self.takeovers.active()
        if active is not None:
            inst = self._by_id.get(active.instance_id)
            if inst is None:
                self.takeovers.pop(active.instance_id)
                return
            if self.slot is None or self.slot.instance is not inst or self.phase is not Phase.TAKEOVER:
                self._start_slot(inst, t, duration=INF, phase=Phase.TAKEOVER)
        elif self.phase is Phase.TAKEOVER:
            self._advance(t, self.slot.instance if self.slot else None)

    def _candidates(self) -> list[ModuleInstance]:
        return list(self._rotation)

    def _pick_next(self, after: ModuleInstance | None, t: float, backwards: bool = False) -> ModuleInstance | None:
        cands = self._candidates()
        if not cands:
            return self._idle_if_displayable(t)
        if self._pinned is not None:
            pinned = self._by_id.get(self._pinned)
            if pinned is not None:
                return pinned
        start = 0
        if after is not None:
            ids = [c.instance_id for c in cands]
            if after.instance_id in ids:
                start = ids.index(after.instance_id) + (-1 if backwards else 1)
            elif backwards:
                start = -1
        n = len(cands)
        for k in range(n):
            idx = (start + (-k if backwards else k)) % n
            inst = cands[idx]
            if not inst.available(t):
                continue
            if inst is after and n > 1:
                continue
            if self._should_display(inst, t):
                return inst
        return self._idle_if_displayable(t)

    def _idle_if_displayable(self, t: float) -> ModuleInstance | None:
        idle = self._idle
        if idle is not None and idle.available(t) and self._should_display(idle, t):
            return idle
        return None

    def _should_display(self, inst: ModuleInstance, t: float) -> bool:
        try:
            return bool(inst.module.should_display())
        except Exception as exc:
            self._fail(inst, t, exc)
            return False

    def _advance(self, t: float, after: ModuleInstance | None, backwards: bool = False) -> Slot | None:
        nxt = self._pick_next(after, t, backwards=backwards)
        if nxt is None:
            self._end_slot(t)
            self._blank_checked_at = t
            return None
        if self.slot is not None and nxt is self.slot.instance and len(self._candidates()) <= 1:
            # Only one module: restart its slot without a transition.
            self.slot.started_at = t
            return self.slot
        self._start_slot(nxt, t)
        return self.slot

    def _end_slot(self, t: float) -> None:
        if self.slot is not None:
            try:
                self.slot.instance.module.on_exit()
            except Exception as exc:
                self._fail(self.slot.instance, t, exc)
            self.slot = None

    def _start_slot(
        self, inst: ModuleInstance, t: float, *, duration: float | None = None, phase: Phase | None = None
    ) -> None:
        prev_frame = self.slot.last_frame if self.slot is not None else self._last_output
        self._end_slot(t)
        try:
            inst.module.on_enter()
            fps = int(inst.module.fps())
        except Exception as exc:
            self._fail(inst, t, exc)
            return
        self.slot = Slot(
            instance=inst,
            started_at=t,
            duration=duration if duration is not None else inst.duration(self.default_duration),
            fps=max(0, fps),
        )
        if phase is Phase.TAKEOVER:
            self.phase = Phase.TAKEOVER
            self._prev_frame = None
        elif prev_frame is not None and self.transition.duration > 0:
            self.phase = Phase.TRANSITION
            self._prev_frame = prev_frame
            self._transition_start = t
        else:
            self.phase = Phase.SHOWING
            self._prev_frame = None
        self._on_event(ModuleChanged(instance_id=inst.instance_id, phase=self.phase.value))

    def _render_slot(self, slot: Slot, t: float) -> Image.Image | None:
        due = (
            slot.last_frame is None or slot.dirty or (slot.fps > 0 and t - slot.last_render_at >= 1.0 / slot.fps - 1e-6)
        )
        if not due:
            return slot.last_frame
        dt = 0.0 if slot.last_frame is None else t - slot.last_render_at
        frame_info = FrameInfo(
            now=self._now(),
            monotonic=t,
            dt=dt,
            index=slot.frame_index,
            slot_elapsed=t - slot.started_at,
            slot_duration=slot.duration,
        )
        self._canvas.clear()
        try:
            slot.instance.module.render(self._canvas, frame_info)
        except Exception as exc:
            self._fail(slot.instance, t, exc)
            self._advance(t, slot.instance)
            return None
        slot.instance.health.mark_ok()
        slot.last_frame = self._canvas.snapshot()
        slot.last_render_at = t
        slot.frame_index += 1
        slot.dirty = False
        return slot.last_frame

    def _deliver_inputs(self, slot: Slot) -> None:
        while True:
            try:
                ev = self._inputs.get_nowait()
            except queue.Empty:
                return
            if self.phase is Phase.TAKEOVER or slot.instance.info.accepts_input:
                try:
                    slot.instance.module.handle_input(ev)
                except Exception as exc:
                    log.warning("input handler failed for %s: %s", slot.instance.instance_id, exc)

    def _fail(self, inst: ModuleInstance, t: float, exc: BaseException) -> None:
        msg = f"{type(exc).__name__}: {exc}"
        inst.health.mark_failed(t, msg)
        log.error("module %s failed: %s\n%s", inst.instance_id, msg, "".join(traceback.format_exception(exc)).rstrip())
        self._on_event(ModuleError(instance_id=inst.instance_id, message=msg))
        self.takeovers.pop(inst.instance_id)
