import asyncio
import queue

from PIL import Image

from homely.core.events import ConfigChanged, EventBus, ModuleError
from homely.core.takeover import Takeover, TakeoverStack
from homely.core.transitions import Slide, make_transition


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
