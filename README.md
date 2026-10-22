# Ambideck

A [Decky Loader](https://decky.xyz) plugin that turns compatible handheld-PC lights into an Ambilight.
While you play, the lights follow the screen using four zones, left/right colours or one shared colour,
depending on the device. The video below shows the ROG Xbox Ally.

https://github.com/user-attachments/assets/d378b852-994a-4eab-8c60-6a79b5997024

## What it does

- **Follows the screen** in any game: four corners or two screen sides, combined to fit the device's RGB zones.
- **Keeps colours alive:** colourful pixels count more than grey ones, and dim scenes are lifted, so pastel and
  dark scenes keep their tint.
- **Dark scenes:** a near-black corner leaves a faint glow, or switches its half of the ring off.
- **Hands the lights back** when you stop playing: to [HueSync](https://github.com/honjow/HueSync)'s setting if
  you use it on Ally, otherwise to the controller's native rainbow or a single static colour.
- **Per game:** switch it off for games where it distracts.
- **Outside games:** off, your normal lights, or follow the screen just like in a game. Following outside games
  keeps the capture running whenever Game Mode is up: about 7 % of one CPU core and roughly 0.2 W.
- **Docked:** off by default; one switch to keep it on.
- **Light on resources:** gamescope hands over a tiny 128×72 frame; about 7 % of one CPU core in total.
- **Updates itself:** tells you when a new release is out and installs it through Decky.
- **Makes way for screen recorders:** while a recorder such as [Showreel](https://github.com/michpalm/showreel)
  holds the capture lock, Ambideck lets go of gamescope's screen stream and hands the lights back
  (see [Screen recorders](#screen-recorders)).

## Install

Ambideck is not in the Decky plugin store. In Game Mode:

1. Decky → Settings → General → turn on **Developer mode**.
2. Download `ambideck.zip` from the [latest release](../../releases/latest).
3. Decky → Settings → Developer → **Install plugin from ZIP**.

## Settings

Quick Access (…) → Ambideck: on/off, **In this game**, **Layout** (Corners or Sides), **Brightness**,
**Colour boost**, **Speed** (Smooth, Balanced, Fast), **Outside games** (Off, Normal colour, Follow),
**Dark scenes** (Glow, Off) and **Run when docked**.

<img src="docs/images/quick-access.png" alt="Ambideck in Quick Access" width="320">

## Updates

Once a day Ambideck asks GitHub for the latest release. When there is a newer one, Quick Access → Ambideck shows
**Update to X.Y.Z**: press **Update** and confirm in Decky's dialog. Decky checks the download against the
release's SHA-256 and keeps your settings. **Check for updates** asks right away.

## How it works

![How Ambideck turns a frame into ring colours](docs/images/how-it-works.png)

This is a real frame from the device, run through Ambideck's own colour code:

1. gamescope (Steam's compositor) shrinks every frame to 128×72 on the GPU and hands it over through PipeWire.
2. The frame is split into four corners, one per half ring, and every 4th pixel of each corner is read.
3. Colourful pixels are weighted more than grey ones, then the colour boost raises the saturation.
4. The ring's brightness follows the corner's brightness on a curve that lifts dim scenes, with a small minimum
   glow (or off, with Dark scenes = Off).
5. Colours fade smoothly between frames and jump on scene cuts. A device-specific backend combines samples
   to fit the available zones and sends them through HID, serial or the kernel's multicolour LED interface.

On Ally, when Ambideck takes over, it asks HueSync to step aside; when it stops, it asks HueSync to re-apply your setting
for the current game and power state. Both go through HueSync's own backend, and no HueSync code is copied.
Other devices use their native rainbow where documented, or one static colour averaged from the last screen
colours (soft white before the first frame). The Off setting still turns the lights off.

## Screen recorders

gamescope has a single screen stream, and the first app reading it sets its size for every reader. Ambideck asks
for a tiny frame, so a recorder that joins later would record at 128×72. Disconnecting a full-size reader while a game
is drawing can also crash gamescope on SteamOS 3.8.

So recorders can ask Ambideck to step aside: write `/run/decky-screen-capture.lock` as root, containing
`{"pid": <recorder pid>, "owner": "<name>"}`. Ambideck checks it every 0.5 s, and again right before every connection,
and stays off the stream while the lock exists and that process is alive (zombies count as dead). Remove the lock only
after your recorder has disconnected from gamescope. [Showreel](https://github.com/michpalm/showreel) does this.

## Compatibility

Earlier releases were tested on a ROG Xbox Ally (RC73YA) running Bazzite and SteamOS 3.8, handheld and docked
to a TV. This change adds the following protocol implementations; **the new backends and output worker
still need hardware validation**.

| Device family | Lighting |
| --- | --- |
| ROG Ally family | Existing four-zone HID protocol; original Ally/Ally X zone order remains untested |
| Legion Go / Go 2 | Left and right ring colours |
| Legion Go S | One shared colour |
| MSI Claw A1M, 7/8 AI+, 8 EX AI+, A8 | One shared colour; USB firmware revision selects the RGB address |
| AYANEO, AYN Loki, Zotac Zone | One shared colour where a compatible kernel RGB LED interface exists |
| Selected OneXPlayer / OneXFly / AOKZOE A1X | One shared colour through an explicitly matched HID/USB-serial protocol |

Quick Access shows the detected device and its available zones. Controllers are rediscovered after disconnects.
Unknown models and ambiguous interfaces receive no RGB commands. See [RGB protocols](docs/rgb-protocols.md)
for exact model matching and exclusions. HHD and InputPlumber are protocol references, not dependencies.
Other RGB software can overwrite the lights; Ambideck does not stop or reconfigure controller daemons.

## Development

```bash
pnpm install
pnpm test
python3 -m venv .venv && .venv/bin/pip install pytest && .venv/bin/pytest tests/py
scripts/package.sh   # builds out/ambideck.zip
```

`scripts/serve.sh` serves the zip on your network for **Install plugin from URL**.
`scripts/demo-capture.py` and `scripts/demo-render.py` make the picture in How it works (and a video of it).
[docs/device-checklist.md](docs/device-checklist.md) lists what to check on the device.
Releases are tagged `vX.Y.Z` and carry the package as `ambideck.zip`; the updater relies on both.

## About this project

A personal project, maintained on a best-effort basis. The code was written with [Claude](https://claude.ai)
(Anthropic's AI), directed, reviewed and tested on device by the author.

## Support

Ambideck is free. If you'd like to support its development, you can do so on Ko-fi. It's entirely optional: bug
reports and ideas are just as welcome.

[![Support Ambideck on Ko-fi](https://ko-fi.com/img/githubbutton_sm.svg)](https://ko-fi.com/michpalm)

## Credits

- ROG Ally light protocol as documented by [HHD](https://github.com/hhd-dev/hhd) and the Linux `hid-asus-ally`
  driver (Luke D. Jones, Denis Benato).
- Other handheld protocol and device information from [HHD](https://github.com/hhd-dev/hhd) and
  [InputPlumber](https://github.com/ShadowBlip/InputPlumber); independently implemented here.
- Works alongside [HueSync](https://github.com/honjow/HueSync) by honjow through its public backend methods.
- Demo footage: Ori and the Blind Forest: Definitive Edition by Moon Studios / Xbox Game Studios.
- Not affiliated with ASUS, Microsoft, Valve, Philips or any game shown.

## License

[MIT](LICENSE)
