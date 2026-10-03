"""Render recorded frames (scripts/demo-capture.py) into a video and GIF that show how Ambideck turns a frame into
ring colours, using the real colour code. Needs Pillow and ffmpeg.
Usage: python3 scripts/demo-render.py frames.bin out-basename   → out-basename.mp4 and out-basename.gif"""
import os
import struct
import subprocess
import sys
import tempfile

from PIL import Image, ImageDraw, ImageFont

ROOT = os.path.abspath(os.path.join(os.path.dirname(__file__), ".."))
sys.path.insert(0, os.path.join(ROOT, "py_modules"))
from ambideck.colour import (SAMPLE_STEP, SPEEDS, Smoother, analyse, boost, boost_factor, is_cut,  # noqa: E402
                             region_colour, regions, to_led)

SETTINGS = {"layout": "corners", "brightness": 70, "boost": 58, "speed": "balanced"}
SCALE, W, H = 6, 1280, 720
NAMES = ["Left bottom", "Left top", "Right top", "Right bottom"]


def font(size, bold=False):
    name = "Arial Bold.ttf" if bold else "Arial.ttf"
    try:
        return ImageFont.truetype(f"/System/Library/Fonts/Supplemental/{name}", size)
    except OSError:
        return ImageFont.load_default()


FONT, SMALL, BIG = font(18), font(14), font(22, True)


def read_frames(path):
    raw, off, frames = open(path, "rb").read(), 0, []
    while off < len(raw):
        t, w, h, stride = struct.unpack_from("<dIII", raw, off)
        (n,) = struct.unpack_from("<I", raw, off + 20)
        frames.append((t, w, h, stride, raw[off + 24: off + 24 + n]))
        off += 24 + n
    return frames


def seen(led):  # how an LED value looks to the eye (undo the gamma the controller needs)
    return tuple(int(255 * (c / 255) ** (1 / 2.2)) for c in led)


def plain_mean(frame, stride, rect):
    x0, y0, x1, y1 = rect
    s, n = [0, 0, 0], 0
    for y in range(y0, y1):
        for x in range(x0, x1):
            i = y * stride + x * 4
            s[0] += frame[i + 2]
            s[1] += frame[i + 1]
            s[2] += frame[i]
            n += 1
    return tuple(v // n for v in s)


def render(frames, outdir):
    smoother, prev = Smoother(), None
    for k, (t, w, h, stride, data) in enumerate(frames):
        a = analyse(data, w, h, stride, SETTINGS["layout"], SETTINGS["boost"], SETTINGS["brightness"])
        cut = is_cut(prev, a.frame_level)
        prev = a.frame_level
        leds = [to_led(v) for v in smoother.step(a.targets, t, SPEEDS[SETTINGS["speed"]][0], cut)]
        img = Image.new("RGB", (W, H), (18, 18, 22))
        d = ImageDraw.Draw(img)
        fx, fy = 24, 60
        frame = Image.frombuffer("RGBX", (w, h), data, "raw", "BGRX", stride, 1).convert("RGB")
        img.paste(frame.resize((w * SCALE, h * SCALE), Image.NEAREST), (fx, fy))
        d.text((fx, 20), f"What Ambideck sees: the {w}×{h} frame from gamescope, enlarged", fill=(230, 230, 230), font=FONT)
        for y in range(0, h, SAMPLE_STEP * 2):  # half of the sample grid, so it stays readable
            for x in range(0, w, SAMPLE_STEP * 2):
                d.point((fx + x * SCALE + SCALE // 2, fy + y * SCALE + SCALE // 2), fill=(255, 255, 255))
        mx, my = fx + w * SCALE // 2, fy + h * SCALE // 2
        d.line([(mx, fy), (mx, fy + h * SCALE)], fill=(255, 255, 255), width=2)
        d.line([(fx, my), (fx + w * SCALE, my)], fill=(255, 255, 255), width=2)
        for i, (lx, ly) in enumerate([(fx + 8, my + 8), (fx + 8, fy + 8), (mx + 8, fy + 8), (mx + 8, my + 8)]):
            d.rectangle([lx, ly, lx + 132, ly + 26], fill=(0, 0, 0))
            d.text((lx + 6, ly + 5), NAMES[i], fill=(255, 255, 255), font=SMALL)
            d.rectangle([lx + 106, ly + 4, lx + 126, ly + 22], fill=seen(leds[i]), outline=(255, 255, 255))
        py = fy + h * SCALE + 24
        d.text((fx, py), "Per corner:  plain average  →  colourful pixels weighted  →  colour boost  →  ring",
               fill=(230, 230, 230), font=FONT)
        for i, rect in enumerate(regions(w, h, "corners")):
            rgb, _ = region_colour(data, stride, rect)
            steps = [plain_mean(data, stride, rect), tuple(int(c) for c in rgb),
                     tuple(int(c) for c in boost(rgb, boost_factor(SETTINGS["boost"]))), seen(leds[i])]
            x, y = fx + (i % 2) * 380, py + 34 + (i // 2) * 52
            d.text((x, y + 10), NAMES[i], fill=(200, 200, 200), font=SMALL)
            for j, c in enumerate(steps):
                d.rectangle([x + 100 + j * 64, y, x + 150 + j * 64, y + 40], fill=c, outline=(90, 90, 90))
        px = 840
        d.text((px, 20), "Stick rings", fill=(230, 230, 230), font=BIG)
        for cx, (top, bottom), label in ((px + 100, (leds[1], leds[0]), "Left stick"), (px + 310, (leds[2], leds[3]), "Right stick")):
            cy, r = 250, 85
            d.pieslice([cx - r, cy - r, cx + r, cy + r], 180, 360, fill=seen(top))
            d.pieslice([cx - r, cy - r, cx + r, cy + r], 0, 180, fill=seen(bottom))
            d.ellipse([cx - r + 18, cy - r + 18, cx + r - 18, cy + r - 18], fill=(30, 30, 34))
            d.ellipse([cx - 34, cy - 34, cx + 34, cy + 34], fill=(55, 55, 60))
            d.text((cx - 44, cy + r + 14), label, fill=(220, 220, 220), font=FONT)
        lines = [f"t = {t:4.1f} s", "scene cut: colours jump" if cut else "colours fade (Balanced)",
                 "brightness 70 · boost 58", "", "Sent to the controller:"]
        lines += [f"  {NAMES[i]:12s} {leds[i]}" for i in range(4)]
        for n, line in enumerate(lines):
            d.text((px, 420 + n * 24), line, fill=(255, 210, 120) if "cut:" in line else (210, 210, 210),
                   font=SMALL if n > 4 else FONT)
        img.save(os.path.join(outdir, f"f{k:04d}.png"))


def main():
    src, out = sys.argv[1], sys.argv[2]
    frames = read_frames(src)
    fps = len(frames) / max(0.001, frames[-1][0] - frames[0][0])
    with tempfile.TemporaryDirectory() as tmp:
        render(frames, tmp)
        pattern = os.path.join(tmp, "f%04d.png")
        subprocess.run(["ffmpeg", "-y", "-loglevel", "error", "-framerate", f"{fps:.2f}", "-i", pattern, "-c:v", "libx264",
                        "-pix_fmt", "yuv420p", "-crf", "20", f"{out}.mp4"], check=True)
        subprocess.run(["ffmpeg", "-y", "-loglevel", "error", "-framerate", f"{fps:.2f}", "-i", pattern, "-vf",
                        "fps=10,scale=720:-1:flags=lanczos,split[a][b];[a]palettegen=max_colors=96:stats_mode=diff[p];"
                        "[b][p]paletteuse=dither=bayer:bayer_scale=4:diff_mode=rectangle",
                        f"{out}.gif"], check=True)
    print(f"{len(frames)} frames at {fps:.1f} fps → {out}.mp4, {out}.gif")


if __name__ == "__main__":
    main()
