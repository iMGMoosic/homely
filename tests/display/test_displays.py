import asyncio
import io
import sys
import types

from PIL import Image

from homely.config.models import PanelConfig
from homely.display.composite import CompositeDisplay
from homely.display.framebus import ENC_RGB, HEADER, FrameBus, encode_packet
from homely.display.recording import RecordingDisplay
from homely.display.rgbmatrix import OPTION_FIELDS, RgbMatrixDisplay, pixel_mapper_for
from homely.render.size import Size


def test_framebus_publish_and_encode():
    async def main():
        bus = FrameBus()
        sub = bus.subscribe()
        assert await sub.wait_for_new(-1, timeout=0.01) is None
        img = Image.new("RGB", (8, 4), (1, 2, 3))
        bus.set_brightness(42)
        bus.publish(img)
        pkt = await sub.wait_for_new(0, timeout=1)
        assert pkt is not None and pkt.seq == 1 and pkt.brightness == 42
        data = bus.encoded(pkt)
        ver, enc, w, h, seq, br = HEADER.unpack(data[: HEADER.size])
        assert (ver, enc, w, h, seq, br) == (1, 0, 8, 4, 1, 42)
        decoded = Image.open(io.BytesIO(data[HEADER.size :]))
        assert decoded.convert("RGB").getpixel((0, 0)) == (1, 2, 3)
        raw = encode_packet(pkt, ENC_RGB)
        assert len(raw) == HEADER.size + 8 * 4 * 3
        assert bus.encoded(pkt) is data  # cached
        sub.close()
        assert not bus.has_subscribers

    asyncio.run(main())


def test_composite_and_recording():
    a, b = RecordingDisplay(Size(4, 4)), RecordingDisplay(Size(4, 4))
    comp = CompositeDisplay([a, b])
    comp.open()
    comp.show(Image.new("RGB", (4, 4), (5, 5, 5)))
    comp.set_brightness(7)
    assert a.last.getpixel((0, 0)) == (5, 5, 5) and b.shown == 1 and b.brightness == 7


def test_pixel_mapper_composition():
    cfg = PanelConfig(pixel_mapper_config="U-mapper", orientation="portrait", rotate_direction=270)
    assert pixel_mapper_for(cfg) == "U-mapper;Rotate:270"
    assert pixel_mapper_for(PanelConfig()) == ""
    assert cfg.logical == Size(64, 64)
    assert PanelConfig(rows=32, cols=64, orientation="portrait").logical == Size(32, 64)


def test_rgbmatrix_display_with_fake_module(monkeypatch):
    calls = {}

    class Options:
        pass

    class Canvas:
        def SetImage(self, img, x, y, unsafe):
            calls["set"] = (img.mode, img.size, unsafe)

    class Matrix:
        def __init__(self, options):
            calls["options"] = options
            self.width, self.height = 64, 64
            self.brightness = 0

        def CreateFrameCanvas(self):
            return Canvas()

        def SwapOnVSync(self, canvas):
            calls["swap"] = calls.get("swap", 0) + 1
            return canvas

        def Clear(self):
            pass

    fake = types.ModuleType("rgbmatrix")
    fake.RGBMatrixOptions = Options
    fake.RGBMatrix = Matrix
    monkeypatch.setitem(sys.modules, "rgbmatrix", fake)

    cfg = PanelConfig(hardware_mapping="adafruit-hat-pwm", gpio_slowdown=3, gamma=2.2)
    d = RgbMatrixDisplay(cfg, initial_brightness=50)
    d.open()
    opts = calls["options"]
    for name in OPTION_FIELDS:
        assert getattr(opts, name) == getattr(cfg, name)
    assert opts.brightness == 50
    d.show(Image.new("RGB", (64, 64), (128, 128, 128)))
    assert calls["set"] == ("RGB", (64, 64), True) and calls["swap"] == 1
    d.set_brightness(10)
    d.close()
