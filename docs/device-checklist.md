# Ambideck device checklist

Run after installing a new build (Decky → Developer → Install plugin from URL, `scripts/serve.sh`).

| # | Check | Expected |
|---|---|---|
| 1 | Quick Access → Ambideck | All controls shown; "In this game" only while a game runs |
| 2 | Start a colourful game | Rings follow the screen within ~1 s; top/bottom halves follow top/bottom |
| 3 | Layout → Sides | Each ring one colour for its side |
| 4 | Pastel scene (e.g. Neva title) | Colours clearly tinted, not white |
| 5 | Dark scene / loading screen | Faint glow, never fully off |
| 6 | Speed Smooth / Balanced / Fast in a fast game | Visibly calmer / default / snappier; no flicker on Fast |
| 7 | Brightness 10 and 100 | Very dim / full |
| 8 | Quit the game | HueSync's setting comes back within ~1 s |
| 9 | Ambideck off mid-game | HueSync's setting comes back |
| 10 | "In this game" off, quit, restart the same game | Stays off for that game; other games still follow |
| 11 | Charger plugged in mid-game (HueSync gradient) | Ambideck keeps the lights, no fighting; after quitting, gradient resumes |
| 12 | Sleep mid-game, wake | Rings follow again after wake |
| 13 | Outside games = Off | Rings dark in menus; game still follows |
| 14 | Outside games = Artwork, open a game page | Rings take the artwork's colours; leaving the page hands back |
| 15 | Dock with Run when docked off / on | Hands back / keeps following |
| 16 | Disable HueSync in Decky, quit a game | Rainbow |
| 17 | Start and quit a game 5 times | `journalctl --user -b \| grep "\[gamescope\].*pipewire" \| tail -3` never shows `error`; Steam recording still works |
| 18 | CPU while following | gamescope + Ambideck within ~6 % of one core over baseline |
| 19 | Battery on battery power, 10 min, Ambideck on vs off | Difference under ~0.3 W |
| 20 | HDR game (when the new dock is in) | Colours look right, not washed out |
