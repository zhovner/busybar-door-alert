// Door Alert — BUSY Bar app.
// Launched by Home Assistant (or any script) with one request:
//   POST /api/apps/launch?app_id=app.home.door_alert
// Plays the sparkle chime, blinks the status LED, and loops a pixel door
// swinging open (a stick figure in the doorway) next to "DOOR / OPENED" with a
// light running around the box. Everything runs on the device; nothing is
// streamed over Wi-Fi. When done its elements time out and the script ends.
//
// Notes:
//  * Firmware 1.3.1 reboots if fetch() is called inside a setInterval callback
//    after clearInterval() on that interval, so the final redraw runs in a
//    fresh setTimeout (see the busybar-js-reboot-repro bug report).
//  * Apps may not call /api/apps/launch (not in the allowed endpoint list), and
//    when the script ends the device shows this app's Start/Setup card, so the
//    trigger script (door_alert.py) relaunches the Clock afterwards.

const APP_ID = "app.home.door_alert";
const API = "http://127.0.0.1/api";
const PRIORITY = 100;            // above the Clock (90); an active BUSY session is 90 too
const TICK_MS = 100;
const FRAME_TIMEOUT = 3;         // seconds; frames vanish by themselves if the app dies
const LED = "#FFB000FF";         // amber
const SOUND = "sounds/sparkle_chime.snd";
const DEFAULTS = { duration: 30, sound: true };

// ------------------------------------------------------------------ pixel art
const PAL = {
  ".": "#000000", F: "#8A5E3A", D: "#B0662A", d: "#7A4019", K: "#FFD700",
  P: "#FFFFFF", b: "#0B4A18", m: "#2FA845", M: "#9DFFAE",
};

// Door bitmap covers display columns 3..16 (14 px) and all 16 rows.
const DOOR_X = 3, DOOR_W = 14, DOOR_H = 16;
const FX0 = 0, FX1 = 13;         // jambs (local coords)
const DY0 = 1, DY1 = 15;         // doorway rows
const HINGE = FX0 + 1;
// (panel width, how far the free edge recedes top/bottom): closed -> open
const OPENING = [[12, 0], [11, 0], [9, 1], [7, 1], [5, 2], [3, 2], [2, 3]];
// one open/close cycle, in ticks
const CYCLE = [0, 0, 0, 0, 0, 0, 1, 2, 3, 4, 5,
  6, 6, 6, 6, 6, 6, 6, 6, 6, 6, 6, 6, 6, 5, 4, 3, 2, 1];
// xkcd-style stick figure (local x 4, y 2)
const PERSON = [
  "..PPP..", ".P...P.", ".P...P.", ".P...P.", "..PPP..", "...P...", "..PPP..",
  ".P.P.P.", "P..P..P", "...P...", "...P...", "..P.P..", ".P...P.", "P.....P",
];
const PERSON_X = 4, PERSON_Y = 2;

// Label box around "OPENED": display x 28..60, y 7..15
const BOX_X = 28, BOX_Y = 7, BOX_W = 33, BOX_H = 9;
const RUN_LEN = 9, RUN_STEP = 3;

function grid(w, h) {
  const g = [];
  for (let y = 0; y < h; y++) g.push(new Array(w).fill("."));
  return g;
}

function toXpm(g) {
  const w = g[0].length, h = g.length;
  const rows = g.map((r) => r.join(""));
  const used = Object.keys(PAL).filter((c) => rows.some((r) => r.indexOf(c) >= 0));
  return ["! XPM2", `${w} ${h} ${used.length} 1`]
    .concat(used.map((c) => `${c} c ${PAL[c]}`), rows).join("\n") + "\n";
}

function doorFrame(width, recede) {
  const g = grid(DOOR_W, DOOR_H);
  for (let x = FX0; x <= FX1; x++) g[0][x] = "F";
  for (let y = 0; y < DOOR_H; y++) { g[y][FX0] = "F"; g[y][FX1] = "F"; }
  PERSON.forEach((row, dy) => {
    for (let dx = 0; dx < row.length; dx++) if (row[dx] === "P") g[PERSON_Y + dy][PERSON_X + dx] = "P";
  });
  for (let i = 0; i < width; i++) {
    const x = HINGE + i;
    const s = Math.round(recede * i / Math.max(width - 1, 1));
    for (let y = DY0 + s; y <= DY1 - s; y++) g[y][x] = "D";
  }
  if (width >= 7) {
    const x0 = HINGE + 2, x1 = HINGE + width - 3;
    for (const y of [3, 4, 5, 6, 10, 11, 12, 13])
      for (let x = x0; x <= x1; x++)
        if (y === 3 || y === 6 || y === 10 || y === 13 || x === x0 || x === x1) g[y][x] = "d";
    g[8][HINGE + width - 2] = "K";
  } else {
    const x = HINGE + width - 1;
    for (let y = DY0; y <= DY1; y++) if (g[y][x] === "D") g[y][x] = "d";
  }
  return toXpm(g);
}

const DOOR_XPM = OPENING.map(([w, r]) => doorFrame(w, r));

// box perimeter, clockwise, corners skipped (rounded look)
const PATH = (() => {
  const x1 = BOX_W - 1, y1 = BOX_H - 1, p = [];
  for (let x = 1; x < x1; x++) p.push([x, 0]);
  for (let y = 1; y < y1; y++) p.push([x1, y]);
  for (let x = x1 - 1; x > 0; x--) p.push([x, y1]);
  for (let y = y1 - 1; y > 0; y--) p.push([0, y]);
  return p;
})();

function boxFrame(tick) {
  const g = grid(BOX_W, BOX_H);
  for (const [x, y] of PATH) g[y][x] = "b";
  const head = (tick * RUN_STEP) % PATH.length;
  for (let k = 0; k < RUN_LEN; k++) {
    const [x, y] = PATH[(head - k + PATH.length) % PATH.length];
    g[y][x] = k < 3 ? "M" : "m";
  }
  return toXpm(g);
}

// ------------------------------------------------------------------ device API
async function call(method, path, body) {
  const opts = { method, headers: { "Content-Type": "application/json" } };
  if (body !== undefined) opts.body = JSON.stringify(body);
  const res = await fetch(`${API}${path}`, opts);
  if (!res.ok) throw new Error(`${method} ${path}: HTTP ${res.status} ${await res.text()}`);
  return res;
}

const draw = (elements, led) =>
  call("POST", "/display/draw", Object.assign(
    { application_name: APP_ID, priority: PRIORITY, elements },
    led ? { led_notification_color: led } : {}));

async function loadSettings() {
  try {
    const doc = await (await call("GET", `/apps/settings?app_id=${APP_ID}`)).json();
    return Object.assign({}, DEFAULTS, doc.values || {});
  } catch (e) {
    console.error(`${APP_ID}: settings: ${e.message}`);
    return DEFAULTS;
  }
}

function labels(timeout) {
  const t = (id, text, color, y) => ({
    id, type: "text", text, font: "small", color, align: "top_mid",
    x: 45, y, z_index: 1, timeout,
  });
  return [t("label1", "DOOR", "#FFFFFFFF", -1), t("label2", "OPENED", "#3CFF5AFF", 7)];
}

// ------------------------------------------------------------------ main
async function main() {
  const cfg = await loadSettings();
  const durationMs = Math.max(1, cfg.duration) * 1000;
  const started = Date.now();
  let tick = 0, inflight = null, done = false, timer, unbind;

  if (cfg.sound) {
    await call("POST", "/audio/play", { application_name: APP_ID, path: SOUND })
      .catch((e) => console.error(`${APP_ID}: sound: ${e.message}`));
  }

  // Stop the loop, then (in a fresh timer, see the quirks above) redraw every
  // element with a 1 s timeout so the screen clears itself; then the script ends.
  function finish() {
    if (done) return;
    done = true;
    clearInterval(timer);
    setTimeout(async () => {
      if (inflight) await inflight.catch(() => {});
      const fade = (e) => Object.assign({}, e, { timeout: 1 });
      await draw(frameElements(tick).concat(labels(1)).map(fade)).catch(() => {});
      if (unbind) unbind();
    }, 10);
  }

  function frameElements(t) {
    const step = t % CYCLE.length;
    return [
      { id: "door", type: "xpmbitmap", data: DOOR_XPM[CYCLE[step]],
        x: DOOR_X, y: 0, z_index: 0, timeout: FRAME_TIMEOUT },
      { id: "box", type: "xpmbitmap", data: boxFrame(t),
        x: BOX_X, y: BOX_Y, z_index: 0, timeout: FRAME_TIMEOUT },
    ];
  }

  function frame() {
    if (done) return;
    if (Date.now() - started >= durationMs) return finish();
    if (inflight) return;        // previous draw still in flight: skip this tick
    const els = frameElements(tick);
    if (tick === 0) els.push(...labels(Math.ceil(durationMs / 1000)));
    const led = tick % CYCLE.length === 0 ? LED : undefined;   // re-arm the LED every cycle
    tick++;
    inflight = draw(els, led)
      .catch((e) => console.error(`${APP_ID}: draw: ${e.message}`))
      .finally(() => { inflight = null; });
  }

  // Back button ends the alert early.
  unbind = listen("input", (e) => {
    if (e.key === "back" && e.action === "short") setTimeout(finish, 10);
  });
  timer = setInterval(frame, TICK_MS);
}

main().catch((e) => console.error(`${APP_ID}: ${e.message}`));
