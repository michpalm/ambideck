import asyncio
import os

import decky

from ambideck.backend import Backend
from ambideck.capture import GamescopeCapture, session_env
from ambideck.display import charger_connected, external_display_connected
from ambideck.kv import KvStore
from ambideck.lights import Lights, find_hidraw

LOG = "[ambideck]"
KV = KvStore(os.path.join(decky.DECKY_PLUGIN_SETTINGS_DIR, "data.json"))
# The backend runs as root; PipeWire lives in the session user's runtime dir.
os.environ.update(session_env(os.stat(decky.DECKY_USER_HOME).st_uid))
HUESYNC_DIR = os.path.join(os.path.dirname(decky.DECKY_PLUGIN_DIR), "HueSync")


def find_lights():
    path = find_hidraw()
    return Lights(path) if path else None


class Plugin:
    async def _main(self):
        loop = asyncio.get_running_loop()

        def emit(event, *args):
            asyncio.run_coroutine_threadsafe(decky.emit(event, *args), loop)

        self.backend = Backend(
            find_lights=find_lights,
            docked=external_display_connected,
            charger=charger_connected,
            emit=emit,
            make_capture=lambda on_frame, on_state, hz: GamescopeCapture(on_frame, on_state, max_hz=hz),
            huesync_installed=lambda: os.path.isdir(HUESYNC_DIR),
        )
        self.backend.start_worker()
        decky.logger.info(f"{LOG} backend started")

    async def _unload(self):
        self.backend.shutdown()
        decky.logger.info(f"{LOG} backend stopped")

    async def kv_get(self, key: str):
        return KV.get(key)

    async def kv_set(self, key: str, value) -> None:
        KV.set(key, value)

    async def get_status(self):
        return self.backend.status()

    async def show(self, zones) -> None:
        self.backend.show(zones)

    async def rainbow(self, keep_following: bool = False) -> None:
        self.backend.rainbow(bool(keep_following))

    async def off(self) -> None:
        self.backend.off()

    async def follow(self, settings) -> bool:
        return self.backend.follow(settings)

    async def stop(self) -> None:
        self.backend.stop()

