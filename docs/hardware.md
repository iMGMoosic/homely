# Hardware setup

## Parts

| Part | Notes |
|---|---|
| Raspberry Pi 4 | Raspberry Pi OS Bookworm 64-bit Lite recommended. Pi 3 works with a lower refresh. Pi 5 is supported by the driver upstream but untested with homely. |
| Adafruit RGB Matrix Bonnet | Plugs onto the 40-pin header. |
| HUB75 RGB LED panel | 64x64 P2/P2.5/P3 first; other sizes are supported (see below). |
| 5 V power supply | Separate from the Pi. A 64x64 panel can draw 4 A at full white. Power the panel from the Bonnet's screw terminals. |

## Bonnet preparation

1. **64x64 panels need the E address line.** On the Bonnet, bridge the center **E** solder pad to the **8** pad
   (Adafruit panels; some third-party panels use **16**, check the datasheet). Without it you will see the
   top and bottom halves duplicated.
2. **Optional but recommended: the PWM jumper.** Solder a wire between **GPIO4** and **GPIO18** on the Bonnet
   and set `hardware_mapping: adafruit-hat-pwm` in the Hardware tab. This removes flicker. It requires the
   onboard audio to be disabled, which `install.sh` does.

## Raspberry Pi OS settings

`install.sh` applies these; here they are for reference:

- `/boot/firmware/config.txt`: `dtparam=audio=off` (the matrix PWM shares hardware with audio)
- `/etc/modprobe.d/homely-blacklist-audio.conf`: `blacklist snd_bcm2835`
- `/boot/firmware/cmdline.txt`: append `isolcpus=domain,managed_irq,3 nohz_full=3 rcu_nocbs=3 irqaffinity=0,1,2`
  so the refresh thread owns core 3. Optional, but it gives a rock-steady image.

## Tuning

All of these live in the **Display → Hardware** tab (or `/etc/homely/config.yaml` under `panel:`).

| Symptom | Try |
|---|---|
| Flicker or ghosting | `gpio_slowdown`: start at 4, try 3 then 2. Lower is faster but less stable. Set `limit_refresh_rate_hz: 120`. |
| Panel stays dark or shows garbage | `panel_type: FM6126A` (or `FM6127`). Common on newer P2 panels. |
| Colors swapped | `led_rgb_sequence: RBG` (or another permutation). |
| Top/bottom halves duplicated on 64x64 | Bridge the E pad (see above); check `row_address_type: 0`. |
| Washed-out colors | `gamma: 2.2`. |
| Image mirrored or rotated | `pixel_mapper_config: Rotate:180` or `Mirror:H`. For portrait mounting use `orientation: portrait`. |
| Odd scan patterns (outdoor panels) | `multiplexing: 1..17`, see the [driver docs](https://github.com/hzeller/rpi-rgb-led-matrix#panel-types). |

## Multiple panels

Chain panels and set `chain_length` (side by side) or `parallel` (extra chains on the Bonnet's single
connector are not possible; that needs a different HAT). For a 2x2 arrangement of 64x64 panels giving
128x128, use `chain_length: 4` with `pixel_mapper_config: U-mapper`.

## Supported logical sizes

64x64, 32x32, 64x32, 128x32, 128x64, 128x128, and portrait 32x64, 32x128, 64x128. Every module has a
64x64 design first; other sizes get dedicated layouts over time, with a size-agnostic fallback.
