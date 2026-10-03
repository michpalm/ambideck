"""Record frames exactly as Ambideck receives them, for scripts/demo-render.py.
Run on the device as the session user while a game runs:
  scp -r py_modules/ambideck scripts/demo-capture.py <device>:/tmp/ambideck-demo/
  ssh <device> 'cd /tmp/ambideck-demo && python3 demo-capture.py 8 frames.bin'
File format: per frame <dIII (seconds, width, height, stride) + <I (length) + BGRx bytes."""
import struct
import sys
import time

sys.path.insert(0, ".")
from ambideck.capture import GamescopeCapture  # noqa: E402

seconds = float(sys.argv[1]) if len(sys.argv) > 1 else 8.0
path = sys.argv[2] if len(sys.argv) > 2 else "frames.bin"
count = 0
with open(path, "wb") as out:
    t0 = time.monotonic()

    def on_frame(data, width, height, stride):
        global count
        out.write(struct.pack("<dIII", time.monotonic() - t0, width, height, stride) + struct.pack("<I", len(data)) + data)
        count += 1

    capture = GamescopeCapture(on_frame, lambda state: None, max_hz=15)
    if not capture.start():
        sys.exit("gamescope's video stream is not available")
    time.sleep(seconds)
    capture.stop()
print(f"{count} frames written to {path}")
