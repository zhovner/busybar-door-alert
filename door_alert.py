#!/usr/bin/env python3
"""Show the Door Alert on the BUSY Bar. Run this when the door opens.

The animation, chime, LED and timer all run inside the on-device app
(app.home.door_alert). This script only sends:

  1. POST /api/apps/launch?app_id=app.home.door_alert          (~100 bytes)
  2. when the alert is over: POST /api/apps/quit
     (when an app's script ends, BUSY Bar keeps showing that app's Start/Setup
     card; quitting it returns the device to the mode the selector is set to,
     e.g. OFF -> dark screen. Apps aren't allowed to call /api/apps/* themselves.)

If the launch is refused (the app isn't installed, a higher-priority mode is
active, ...), it falls back to one static frame drawn at priority 100 with the
chime and LED, which expires by itself after the alert duration.

If the door opens again during an alert, the newer run wins and the older one
skips its return step.

  python3 door_alert.py                           launch, wait, quit back to the current mode
  python3 door_alert.py --return-app app.busy.clock   ...then start the Clock instead of quitting
  python3 door_alert.py --no-return               launch only (the app's card stays on screen)
"""
import argparse
import json
import os
import sys
import tempfile
import time

sys.path.insert(0, os.path.join(os.path.dirname(os.path.abspath(__file__)), "tools"))
import busybar  # noqa: E402

APP_ID = "app.home.door_alert"
STATE = os.path.join(tempfile.gettempdir(), "busybar_door_alert.last")

# Fallback frame: open door with the stick figure, label box (72x16 XPM)
FALLBACK_PAL = {".": "#000000", "F": "#8A5E3A", "D": "#B0662A", "d": "#7A4019",
                "P": "#FFFFFF", "m": "#2FA845"}
FALLBACK_ROWS = [
    "...FFFFFFFFFFFFFF.......................................................",
    "...FD...........F.......................................................",
    "...FD....PPP....F.......................................................",
    "...FD...P...P...F.......................................................",
    "...FDd..P...P...F.......................................................",
    "...FDd..P...P...F.......................................................",
    "...FDd...PPP....F.......................................................",
    "...FDd....P.....F............mmmmmmmmmmmmmmmmmmmmmmmmmmmmmmm............",
    "...FDd...PPP....F...........m...............................m...........",
    "...FDd..P.P.P...F...........m...............................m...........",
    "...FDd.P..P..P..F...........m...............................m...........",
    "...FDd....P.....F...........m...............................m...........",
    "...FDd....P.....F...........m...............................m...........",
    "...FD....P.P....F...........m...............................m...........",
    "...FD...P...P...F...........m...............................m...........",
    "...FD..P.....P..F............mmmmmmmmmmmmmmmmmmmmmmmmmmmmmmm............",
]


def duration(default=30):
    status, text = busybar.api("GET", f"/api/apps/settings?app_id={APP_ID}")
    try:
        return int(json.loads(text)["values"]["duration"]) if status == 200 else default
    except (ValueError, KeyError):
        return default


def fallback(seconds):
    xpm = "\n".join(["! XPM2", f"72 16 {len(FALLBACK_PAL)} 1"]
                    + [f"{c} c {v}" for c, v in FALLBACK_PAL.items()] + FALLBACK_ROWS) + "\n"
    text = lambda eid, s, color, y: {"id": eid, "type": "text", "text": s, "font": "small", "color": color,
                                     "align": "top_mid", "x": 45, "y": y, "z_index": 1, "timeout": seconds}
    busybar.api("POST", "/api/audio/play", {"application_name": APP_ID, "path": "sounds/sparkle_chime.snd"})
    return busybar.api("POST", "/api/display/draw", {
        "application_name": APP_ID, "priority": 100, "led_notification_color": "#FFB000FF",
        "elements": [{"id": "door", "type": "xpmbitmap", "data": xpm, "x": 0, "y": 0, "z_index": 0,
                      "timeout": seconds},
                     text("label1", "DOOR", "#FFFFFFFF", -1), text("label2", "OPENED", "#3CFF5AFF", 7)]})


def main():
    ap = argparse.ArgumentParser(description=__doc__, formatter_class=argparse.RawDescriptionHelpFormatter)
    ap.add_argument("--return-app", help="app to start after the alert (default: just quit)")
    ap.add_argument("--no-return", action="store_true", help="do nothing after the alert")
    a = ap.parse_args()

    me = f"{os.getpid()}-{time.time()}"
    with open(STATE, "w") as f:
        f.write(me)

    status, text = busybar.api("POST", f"/api/apps/launch?app_id={APP_ID}")
    print(f"launch {APP_ID}: HTTP {status} {text.strip()}")
    if status != 200:
        status, text = fallback(duration())
        print(f"fallback frame: HTTP {status} {text.strip()}")
        sys.exit(0 if status == 200 else 1)
    if a.no_return:
        return

    time.sleep(duration() + 1.5)
    if open(STATE).read() != me:
        print("a newer alert started; leaving the screen to it")
        return
    if a.return_app:
        status, text = busybar.api("POST", f"/api/apps/launch?app_id={a.return_app}")
        print(f"return to {a.return_app}: HTTP {status} {text.strip()}")
    else:
        status, text = busybar.api("POST", "/api/apps/quit")
        print(f"quit: HTTP {status} {text.strip()}")


if __name__ == "__main__":
    main()
