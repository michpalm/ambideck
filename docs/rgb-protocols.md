# RGB device support

These backends implement protocol information from the pinned sources below.
They have automated protocol and lifecycle tests, but this revision has not
been validated on hardware. Earlier Ally release testing does not establish
that the new output worker is hardware-tested.

## Device matching

| Devices / exact DMI names | Protocol and output |
| --- | --- |
| Ally family exposing `ally:rgb:joystick_rings` | Existing kernel LED-to-hidraw association; four zones |
| Lenovo `83E1` | Legion Go, two sides |
| Lenovo `83N0`, `83N1` | Legion Go 2, two sides; shares the upstream tablet protocol |
| Lenovo `83L3`, `83N6`, `83Q2`, `83Q3` | Legion Go S, shared colour |
| MSI board/product `MS-1T41`, `MS-1T42`, `MS-1T52`, `MS-1T91`, `MS-1T8K` | Claw A1M, 7 AI+, 8 AI+, 8 EX AI+, A8; shared colour |
| `ONEXPLAYER Mini Pro` | OXP HID V2 |
| `ONEXPLAYER F1`, `F1 EVA-01`, `F1L`, `F1 OLED`, `F1Pro`, `F1 EVA-02` (each with `ONEXPLAYER ` prefix) | Mixed protocol's RGB HID V2 interface; does not use the buttons-only serial port |
| `ONEXPLAYER APEX`, `AOKZOE A1X` | Dual protocol's RGB HID V2 interface |
| `ONEXPLAYER X1 mini`, `ONEXPLAYER X1Mini Pro`, `ONEXPLAYER X1Air` | OXP HID V1 |
| `ONEXPLAYER 3`, `ONEXPLAYER X2Mini PRO` | OXP V1 framing, X2 RGB selectors 1/2/7 |
| `ONEXPLAYER G1 i`, `ONEXPLAYER G1 A` | OXP V1 framing over the G1's V2 USB identity |
| `ONEXPLAYER X1 A`, `ONEXPLAYER X1z`, `ONEXPLAYER X1Pro`, `ONEXPLAYER X1Pro EVA-02`, `ONEXPLAYER X1 i` | OXP USB serial (CH340 `1a86:7523`), shared colour |
| AYANEO / AYN Loki | Kernel `ayaneo:rgb:joystick_rings`, `ayn:rgb:joystick_rings` or legacy `multicolor:chassis`; shared colour |
| Zotac Zone | Kernel `zotac:rgb:spectra_zone_0/1`; shared colour on both, without assuming physical placement |

Vendor identity is checked alongside DMI for Lenovo, MSI and OneXPlayer
profiles. HID vendor/product IDs alone are insufficient: the report
descriptor must expose the documented application usage. Claw test mode is
excluded; Ambideck never switches controller modes. Claw RGB addresses depend
on the USB firmware revision: 1.66+, 2.17+ and major version 3+ use the newer
address. Missing firmware identity leaves the device unavailable.

Kernel LED backends require the matching handheld vendor and a known RGB node
with readable `multi_index`, `multi_intensity`, `brightness` and
`max_brightness`. Availability depends on the installed kernel driver. Packed
`rgb`/`multi` channels are supported. Unrelated keyboard and charging LEDs are
not selected. AYN's kernel `led_mode` is switched to static when present.

The original AOKZOE A1/A1 Pro/A2 Pro and OneXPlayer 2 variants are excluded,
matching upstream's RGB exclusions. Unknown OneXPlayer models are not guessed.
GPD's full controller-configuration RGB path is excluded from continuous
screen updates. Devices without controllable RGB are unsupported.

## Output and handback

Screen sampling still uses four canonical colours. Two-zone devices combine
the two samples on each side; shared-colour devices average all four. Averages
round halves up. Brightness and gamma are applied once by the existing colour
pipeline. OneXPlayer accent lighting beyond the reported RGB ring capability
remains under firmware control.

Ally retains its 30 Hz ceiling. New HID and kernel LED output caps at 10 Hz,
serial at 5 Hz. OXP requires at least 50 ms between individual reports; a
multi-report update can therefore run slower than that ceiling. Its startup
settling delay is 4 seconds for HID or 2 seconds for serial. These are software
limits derived from upstream timing, not device benchmarks.

Only the newest pending frame is retained. Device discovery and output run in
a separate worker. Lost controllers retry after two seconds, with USB/HID
identity checked again. Unload closes descriptors and serial locks. Serial
output is nonblocking, has a 250 ms write deadline and declines an exclusive
advisory-lock conflict. This lock does not prove another program is absent.

Ally retains HueSync handback. Lenovo and Ally advertise native rainbow;
other backends use a single static colour averaged from the last successfully
displayed frame, or RGB (64,64,64) before one is available. Normal handback
stops periodic writing; temporary capture loss retains capture retries.
Explicit Off remains Off. Settings do not need migration.

Ambideck does not stop HHD or InputPlumber, read controller input, reset
mappings or enable interception. Other RGB writers can still conflict with
it. A serial interface held by another daemon may be unavailable; Ambideck
does not take ownership away from that daemon.

## Sources and tests

HHD revision [`40b6893`](https://github.com/hhd-dev/hhd/tree/40b6893a24371986e4b29df16d4ef2d930741363):

- `src/hhd/device/legion_go/{tablet,slim}/hid.py`: distinct Lenovo report layouts and old-firmware tablet reload requirements.
- `src/hhd/device/claw/{base,const}.py`: model identities, RGB packet and firmware-dependent addresses.
- `src/hhd/device/oxp/{base,const,hid_v1,hid_v2,serial}.py`: exact model routing, framing and timing.
- `src/hhd/controller/physical/rgb.py`: kernel multicolour LED and AYN static-mode interfaces.

InputPlumber revision [`4ed1f50`](https://github.com/ShadowBlip/InputPlumber/tree/4ed1f50c7801e4f91fd17ce1a7b2b9d8d8b82e69):

- `rootfs/usr/share/inputplumber/devices/50-{ayaneo_2,ayaneo_air,ayn_loki_zero,zotac-zone}.yaml`: kernel LED node names.
- `src/input/source/led/multicolor.rs`: channel order and packed RGB format.

Implementations are independent; neither daemon's source is bundled. Golden
report expectations live as literal bytes in `tests/py/test_rgb_*.py`, separate
from production packet construction. Synthetic sysfs trees test detection and
channel metadata, while fake-clock/output tests cover coalescing, fallback,
failure, recovery and shutdown. Frontend tests cover device changes and
HueSync gating. See [device checklist](device-checklist.md) for hardware work.
