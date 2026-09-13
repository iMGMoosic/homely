import asyncio
from datetime import datetime, timedelta

from homely.data.poller import Poller
from homely.data.slot import DataSlot


def test_slot_staleness():
    slot: DataSlot[int] = DataSlot()
    assert not slot.has_value and slot.age(datetime(2026, 1, 1)) is None
    slot.set(1, datetime(2026, 1, 1, 12, 0))
    assert slot.has_value
    assert not slot.is_stale(datetime(2026, 1, 1, 12, 30), timedelta(hours=1))
    assert slot.is_stale(datetime(2026, 1, 1, 14, 0), timedelta(hours=1))
    slot.fail(RuntimeError("x"))
    assert slot.error_count == 1 and slot.value == 1


def test_poller_runs_and_backs_off():
    async def main():
        calls = []

        async def fn():
            calls.append(1)
            if len(calls) == 1:
                raise RuntimeError("first fails")

        p = Poller("t", timedelta(seconds=0.05), fn, jitter=0)
        p.start()
        await asyncio.sleep(0.2)
        await p.stop()
        assert len(calls) >= 2
        assert p.failures == 0 and p.last_error is None

    asyncio.run(main())


def test_poller_trigger_wakes_early():
    async def main():
        calls = []

        async def fn():
            calls.append(1)

        p = Poller("t", timedelta(seconds=60), fn, jitter=0)
        p.start()
        await asyncio.sleep(0.02)
        assert len(calls) == 1
        p.trigger()
        await asyncio.sleep(0.05)
        assert len(calls) == 2
        await p.stop()
        assert not p.running

    asyncio.run(main())
