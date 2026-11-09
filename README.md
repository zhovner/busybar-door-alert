# Door Alert for BUSY Bar

A BUSY Bar app that shows a door-open alert. When it runs, it:

- plays a sparkling bar-chime sound (4.5 s);
- blinks the status LED amber;
- for 30 seconds, loops a pixel door swinging open on a stick figure, next to "DOOR / OPENED" with a light running around the box.

![Door Alert on BUSY Bar](docs/screenshot.png)

It's meant to be triggered by a door sensor, for example an Aqara Door and Window Sensor P2 through Home Assistant.
The animation runs entirely on the device. Each alert takes one ~100-byte HTTP request, so unreliable Wi-Fi doesn't
affect it.

Requires BUSY Bar firmware 1.3.1 or later (HTTP API 27.12+). The tools need only Python 3, no packages.

## Layout

```
src/                     the app, exactly as it's installed on the device
  appmeta/manifest.json  id app.home.door_alert
  appmeta/settings.json  duration (s) and sound on/off, editable on the device
  appmeta/icon_*.png
  scripts/main.js        the app (JerryScript)
  sounds/sparkle_chime.snd
door_alert.py            the trigger: run it when the door opens
tools/build.py           pack src/ into dist/<id>.tgz, install and run it over the HTTP API
tools/make_chime.py      regenerate the sound (+ a .wav preview in dist/)
tools/screenshot.py      save what's on the display as a PNG
tools/busybar.py         tiny HTTP API client used by the tools
```

## Setup

Enable HTTP API access over Wi-Fi on the BUSY Bar, then tell the tools where it is:

```bash
export BUSYBAR_HOST=192.168.1.50      # or put it in ~/.busybar_host
export BUSYBAR_KEY=<access key/token> # or put it in ~/.busybar_key
```

Build and install:

```bash
python3 tools/build.py --install
```

You can also upload `dist/app.home.door_alert.tgz` in the BUSY Bar web interface (Apps tab, then "+ Add app").

## Running it

- **From a script or a home hub:** `python3 door_alert.py`. It launches the app, waits for the alert to finish, then
  quits it, so BUSY Bar goes back to whatever mode the selector is set to (in OFF mode, a dark screen). Use
  `--return-app app.busy.clock` to start an app instead, or `--no-return` to skip that step.
- **Bare HTTP:** `POST http://<busybar>/api/apps/launch?app_id=app.home.door_alert` with the header `X-API-Token: <key>`.
- **On the device:** mode selector → Apps → Door Alert → Start. Press Back to stop early.
- **Web interface:** Apps tab → Door Alert → Start.

The alert's length and whether it plays the sound are app settings: use Setup on the device or the web interface.

## Things to know

- **Ending the alert.** When an app's script ends, BUSY Bar keeps showing that app's Start/Setup screen; it doesn't go
  back to the previous mode. Apps aren't allowed to call `/api/apps/*`, so `door_alert.py` sends
  `POST /api/apps/quit` when the alert is over, which returns the device to the mode the selector is set to. Tested in
  OFF mode: the alert shows and the screen goes dark again afterwards. The API can't report the current mode or app,
  so a previously running app, such as the Clock in Apps mode, isn't restored automatically. Use `--return-app` for
  that.
- **When the app can't start.** If BUSY Bar refuses the launch, `door_alert.py` draws one still frame of the alert
  at priority 100, with the chime and LED. That frame clears itself after the alert duration. Refusal can happen if
  the app isn't installed or a higher-priority mode is active. During a BUSY/CUSTOM session the session owns the
  screen.
- **Firmware 1.3.1 bug:** calling `fetch()` inside a `setInterval` callback after `clearInterval()` on that
  interval reboots the device. `main.js` does its final request from a fresh `setTimeout` instead.

## Notes for BUSY Bar firmware developers

Tested on BB.1, firmware 1.3.1 (build 2026-10-26, commit `8edd2da4`), HTTP API 27.14.0.

### An app can't run as a short "notification" and then give the device back

This app has to show something for 30 seconds and then return the device to whatever it was doing. That can't be
done from inside the app today. It needs a second request from outside, and if that request is lost, the device is
left on the app's screen.

**1. When an app's script ends, the device stays on that app's Start/Setup screen.**

The docs say the app "closes" when nothing is left to wait for. But the device doesn't return to the mode the selector
is set to.

Steps:
1. Set the mode selector to OFF. The screen is dark.
2. `POST /api/apps/launch?app_id=<any app>` for an app that draws for a few seconds, then clears its timers and
   listeners.
3. The app runs. While the selector is in OFF it shows over the dark screen, which works well.
4. When the script ends, the screen shows the app's card ("Door Alert ▸Start / Setup") and stays there.

Expected: the device goes back to OFF, the mode the selector is set to.

Calling `POST /api/apps/quit` over the HTTP API from step 4 does exactly that: the screen goes dark. So the behaviour
exists; it just isn't what happens when an app ends on its own.

**2. An app can't quit itself.**

`/api/apps/*` isn't in the list of endpoints apps may call, and the JS runtime has no `exit()`. Ending the script is
the only way out, and that leads to the card screen in (1).

**3. There's no way to read the current mode or running app.**

No HTTP endpoint reports which mode the selector is set to or which app is running. So an external trigger can't
restore the previous state either. For example, with the Clock running in Apps mode, quitting the alert lands on the
apps menu, not the Clock.

**What would solve it, any one of these:**
- When a script ends on its own, return to the mode the selector is set to, just like `POST /api/apps/quit` does.
- Let an app quit itself: an `exit()` in the runtime, or allow `POST /api/apps/quit` for the calling app.
- A "notification" launch flag that returns to the previous mode or app when the app ends.
- Expose the current mode and running app in `GET /api/status`, so integrations can restore it.

### Other findings

- **Device reboot:** calling `fetch()` inside a `setInterval` callback after `clearInterval()` on that same interval
  reboots the device. There's a minimal repro: a 4-line app, a control app, and a script that detects the reboot.
- **Missing sound returns 200:** `POST /api/audio/play` with a `path` that doesn't exist returns
  `200 {"result":"OK"}`, and `DELETE /api/audio/play` afterwards also returns 200. The OpenAPI spec says 404.
- **Screen capture colours:** `GET /api/screen` returns the frame as BGR, not RGB; the spec says only "base64".
