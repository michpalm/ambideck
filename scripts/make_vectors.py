"""Write tests/vectors/colour.json from the Python colour maths (src/colour.ts must match it).
Usage: python3 scripts/make_vectors.py [--stdout]"""
import json
import os
import sys

ROOT = os.path.abspath(os.path.join(os.path.dirname(__file__), ".."))
sys.path.insert(0, os.path.join(ROOT, "py_modules"))
from ambideck.colour import analyse, quad_frame, to_led  # noqa: E402

CASES = [
    ("primaries", [(0, 0, 255), (255, 0, 0), (0, 255, 0), (255, 255, 0)], "corners", 58, 70),
    ("pastels", [(255, 182, 193), (173, 216, 230), (221, 160, 221), (240, 230, 140)], "corners", 58, 70),
    ("pastels natural", [(255, 182, 193), (173, 216, 230), (221, 160, 221), (240, 230, 140)], "corners", 0, 100),
    ("pastels vivid", [(255, 182, 193), (173, 216, 230), (221, 160, 221), (240, 230, 140)], "corners", 100, 100),
    ("black", [(0, 0, 0)] * 4, "corners", 58, 70),
    ("grey", [(128, 128, 128)] * 4, "corners", 58, 70),
    ("sides", [(0, 0, 255), (255, 0, 0), (0, 255, 0), (255, 255, 0)], "sides", 58, 70),
    ("dim brightness", [(255, 120, 0)] * 4, "corners", 58, 10),
]


def build():
    out = []
    for name, quads, layout, boost_value, brightness in CASES:
        w, h = 16, 8
        a = analyse(quad_frame(w, h, quads), w, h, w * 4, layout, boost_value, brightness)
        out.append({
            "name": name, "width": w, "height": h, "quads": [list(q) for q in quads], "layout": layout,
            "boost": boost_value, "brightness": brightness,
            "targets": [[round(c, 9) for c in t] for t in a.targets], "frameLevel": round(a.frame_level, 9),
            "leds": [list(to_led(t)) for t in a.targets],
        })
    return out


if __name__ == "__main__":
    text = json.dumps(build(), indent=1) + "\n"
    if "--stdout" in sys.argv:
        sys.stdout.write(text)
    else:
        os.makedirs(os.path.join(ROOT, "tests", "vectors"), exist_ok=True)
        with open(os.path.join(ROOT, "tests", "vectors", "colour.json"), "w", encoding="utf-8") as f:
            f.write(text)
