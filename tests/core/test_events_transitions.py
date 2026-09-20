import asyncio
import queue
from typing import get_args

import pytest
from PIL import Image

from homely.config.models import TransitionName
from homely.core.events import ConfigChanged, EventBus, ModuleError
from homely.core.takeover import Takeover, TakeoverStack
from homely.core.transitions import TRANSITION_NAMES, RandomTransition, Slide, make_transition


def test_bus_callback_and_threadsafe_queue():
    bus = EventBus()
    got = []
    unsub = bus.subscribe(got.append, ConfigChanged)
    q, _ = bus.subscribe_threadsafe()
    bus.publish(ConfigChanged(scope="all"))
    bus.publish(ModuleError(instance_id="x", message="m"))
    assert len(got) == 1
    assert q.qsize() == 2
    unsub()
    bus.publish(ConfigChanged(scope="all"))
    assert len(got) == 1


def test_bus_async_queue():
    async def main():
        bus = EventBus()
        q, _ = bus.subscribe_async(ConfigChanged)
        bus.publish(ConfigChanged(scope="rotation"))
        ev = await asyncio.wait_for(q.get(), 1)
        assert ev.scope == "rotation"

    asyncio.run(main())


def test_slide_and_factory():
    prev = Image.new("RGB", (4, 4), (255, 0, 0))
    nxt = Image.new("RGB", (4, 4), (0, 0, 255))
    out = Slide("left").blend(prev, nxt, 0.5)
    assert out.getpixel((0, 0)) == (255, 0, 0) and out.getpixel((3, 0)) == (0, 0, 255)
    assert make_transition("cut", 1).duration == 0
    assert make_transition("fade", 0.4).duration == 0.4
    assert make_transition("slide_up", 0.3).name == "slide_up"


def test_transition_names_match_the_config_schema():
    """Anything the config offers has to be something make_transition can build."""
    assert get_args(TransitionName) == TRANSITION_NAMES
    for name in TRANSITION_NAMES:
        assert make_transition(name, 0.4) is not None
    with pytest.raises(ValueError, match="Unknown transition"):
        make_transition("teleport", 0.4)


@pytest.mark.parametrize("name", [n for n in TRANSITION_NAMES if n != "cut"])
@pytest.mark.parametrize("size", [(128, 32), (64, 64), (32, 128)], ids=str)
def test_every_transition_lands_on_the_next_frame(name, size):
    prev = Image.new("RGB", size, (255, 0, 0))
    nxt = Image.new("RGB", size, (0, 0, 255))
    trans = make_transition(name, 0.4)
    for p in (0.0, 0.1, 0.25, 0.5, 0.75, 0.9, 1.0):
        out = trans.blend(prev, nxt, p)
        assert out.size == size and out.mode == "RGB"
    # By the end the old frame is gone from every corner, so no module leaves a sliver behind.
    end = trans.blend(prev, nxt, 1.0)
    w, h = size
    assert {end.getpixel(c) for c in ((0, 0), (w - 1, 0), (0, h - 1), (w - 1, h - 1))} == {(0, 0, 255)}


def test_random_transition_changes_between_changeovers():
    prev = Image.new("RGB", (32, 32), (255, 0, 0))
    nxt = Image.new("RGB", (32, 32), (0, 0, 255))
    trans = make_transition("random", 0.4)
    assert isinstance(trans, RandomTransition)
    picked = []
    for _ in range(25):
        for p in (0.1, 0.5, 0.9, 1.0):  # one full changeover; p then drops for the next one
            trans.blend(prev, nxt, p)
        picked.append(trans._current.name)
    assert len(set(picked)) > 3, picked


def test_takeover_stack_priority_and_expiry():
    st = TakeoverStack()
    st.push(Takeover("a", priority=1))
    st.push(Takeover("b", priority=5, expires_at=10.0))
    assert st.active().instance_id == "b"
    st.expire(11.0)
    assert st.active().instance_id == "a"
    st.pop("a")
    assert st.active() is None
    assert isinstance(queue.Queue(), queue.Queue)
