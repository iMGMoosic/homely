from __future__ import annotations

from homely.core.scheduler import Phase, Scheduler
from homely.core.transitions import Cut, Fade
from homely.render.size import Size
from tests.conftest import FROZEN, FakeClock
from tests.core.stubs import make_instance

SIZE = Size(8, 8)


def make_sched(transition=None, events=None):
    return Scheduler(
        SIZE,
        transition=transition or Cut(),
        now_fn=lambda: FROZEN,
        default_duration=5.0,
        on_event=(events.append if events is not None else None),
    )


def px(img, x=0, y=0):
    return img.getpixel((x, y))


def test_rotation_advances_after_duration():
    s = make_sched()
    a = make_instance("a", color=(255, 0, 0), duration=2)
    b = make_instance("b", color=(0, 255, 0), duration=3)
    s.apply_rotation([a, b])
    clk = FakeClock()
    f = s.tick(clk.t)
    assert f is not None and px(f) == (255, 0, 0)
    assert s.tick(clk.advance(1.0)) is None  # static: unchanged frame -> None
    f = s.tick(clk.advance(1.0))
    assert f is not None and px(f) == (0, 255, 0)
    assert a.module.exits == 1 and b.module.enters == 1
    f = s.tick(clk.advance(3.0))
    assert f is not None and px(f) == (255, 0, 0)


def test_skip_and_blank():
    s = make_sched()
    a = make_instance("a", display=False)
    b = make_instance("b", color=(1, 2, 3), enabled=False)
    s.apply_rotation([a, b])
    clk = FakeClock()
    f = s.tick(clk.t)
    assert f is not None and px(f) == (0, 0, 0)
    assert s.phase is Phase.BLANK
    assert s.tick(clk.advance(1)) is None
    a.module.display = True
    # Blank re-checks on every tick when a module becomes displayable.
    f = s.tick(clk.advance(6))
    assert f is not None and px(f) == (10, 20, 30)


def test_idle_module_used_when_everyone_declines():
    s = make_sched()
    a = make_instance("a", display=False)
    idle = make_instance("idle", color=(9, 9, 9))
    s.apply_rotation([a], idle)
    f = s.tick(1000.0)
    assert f is not None and px(f) == (9, 9, 9)


def test_static_vs_animated_render_counts():
    s = make_sched()
    static = make_instance("s", fps=0, duration=100)
    s.apply_rotation([static])
    clk = FakeClock()
    for _ in range(10):
        s.tick(clk.advance(0.1))
    assert static.module.renders == 1
    s.invalidate("s")
    s.tick(clk.advance(0.1))
    assert static.module.renders == 2

    s2 = make_sched()
    anim = make_instance("an", fps=10, duration=100)
    s2.apply_rotation([anim])
    clk2 = FakeClock()
    for _ in range(30):
        s2.tick(clk2.advance(1 / 30))
    assert 9 <= anim.module.renders <= 11


def test_render_error_marks_unhealthy_and_continues():
    events = []
    s = make_sched(events=events)
    bad = make_instance("bad", color=(1, 1, 1))
    bad.module.raise_in_render = True
    good = make_instance("good", color=(2, 2, 2))
    s.apply_rotation([bad, good])
    f = s.tick(1000.0)
    assert f is not None and px(f) == (2, 2, 2)
    assert not bad.health.is_healthy(1000.0)
    assert any(type(e).__name__ == "ModuleError" for e in events)
    # After the cooldown it is retried.
    assert bad.health.is_healthy(1000.0 + 61)


def test_fade_transition_blends():
    s = make_sched(transition=Fade(1.0))
    a = make_instance("a", color=(0, 0, 0), duration=1)
    b = make_instance("b", color=(200, 200, 200), duration=10)
    s.apply_rotation([a, b])
    clk = FakeClock()
    s.tick(clk.t)
    f = s.tick(clk.advance(1.0))  # starts transition
    assert s.phase is Phase.TRANSITION
    f = s.tick(clk.advance(0.5))
    assert f is not None and 80 <= px(f)[0] <= 120
    f = s.tick(clk.advance(0.6))
    assert s.phase is Phase.SHOWING
    assert f is not None and px(f) == (200, 200, 200)


def test_pin_and_next():
    s = make_sched()
    a = make_instance("a", color=(1, 0, 0), duration=1)
    b = make_instance("b", color=(0, 1, 0), duration=1)
    s.apply_rotation([a, b])
    clk = FakeClock()
    s.tick(clk.t)
    s.pin("b")
    f = s.tick(clk.advance(0.1))
    assert f is not None and px(f) == (0, 1, 0)
    s.tick(clk.advance(5))  # pinned: does not advance
    assert s.state().current == "b"
    s.pin(None)
    s.next()
    f = s.tick(clk.advance(0.1))
    assert f is not None and px(f) == (1, 0, 0)


def test_takeover_preempts_and_releases():
    s = make_sched()
    a = make_instance("a", color=(1, 0, 0), duration=100)
    game = make_instance("game", color=(0, 0, 9), duration=1)
    s.apply_rotation([a, game])
    clk = FakeClock()
    s.tick(clk.t)
    s.request_takeover("game", 10, None)
    f = s.tick(clk.advance(0.1))
    assert f is not None and px(f) == (0, 0, 9) and s.phase is Phase.TAKEOVER
    s.tick(clk.advance(50))  # duration ignored during takeover
    assert s.state().current == "game"
    s.release_takeover("game")
    f = s.tick(clk.advance(0.1))
    assert s.phase is not Phase.TAKEOVER and s.state().current == "a"


def test_rotation_update_replaces_instance_object():
    s = make_sched()
    a = make_instance("a", color=(1, 1, 1), duration=100)
    s.apply_rotation([a])
    clk = FakeClock()
    s.tick(clk.t)
    a2 = make_instance("a", color=(5, 5, 5), duration=100)
    s.apply_rotation([a2])
    f = s.tick(clk.advance(0.1))
    assert f is not None and px(f) == (5, 5, 5)
    s.apply_rotation([])
    f = s.tick(clk.advance(0.1))
    assert f is not None and px(f) == (0, 0, 0)
