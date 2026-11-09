#!/usr/bin/env python3
"""Synthesize the "sparkling bar chime" sound for the app.

Writes src/sounds/sparkle_chime.snd (the BUSY Bar format: raw signed 16-bit
little-endian mono PCM at 44.1 kHz, no header) and dist/sparkle_chime.wav for
listening on a computer.

The sound: a finger sweeps slowly up a row of small metal rods (2.6 s), the sweep
fades, and it ends on two clean notes (E7, A6), 4.5 s in total. Tuned for the
Busy Bar's small speaker:
  * no overtones above 10 kHz (they whine),
  * rods decay quickly, because closely tuned rods ringing together beat against
    each other at 50-200 Hz, which sounds like a buzz,
  * no detuned "shimmer" copies (they warble).
"""
import math
import os
import random
import struct
import wave

ROOT = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))
SND = os.path.join(ROOT, "src", "sounds", "sparkle_chime.snd")
WAV = os.path.join(ROOT, "dist", "sparkle_chime.wav")

SAMPLE_RATE = 44100
CHIME_SECONDS = 4.5
SWEEP_SECONDS = 2.6                    # length of the rising sweep
SWEEP_FADE = (2.2, 3.0)                # the sweep's ringing fades out over this window...
END_FADE = (4.0, CHIME_SECONDS)        # ...the two closing notes over this one
MAX_PARTIAL_HZ = 10000
PARTIALS = [(1.0, 1.0), (2.756, 0.3)]  # free-free metal bar: fundamental + first overtone
CLOSING_NOTES = [(2.75, 2637.0, 0.55, 0.8),   # E7   (start s, Hz, amplitude, decay s)
                 (3.05, 1760.0, 0.75, 1.0)]   # A6
PEAK = 0.55                            # of full scale; the device volume does the rest


def strikes():
    rnd = random.Random(7)
    n, lo, hi = 40, 1800.0, 6500.0
    rods = [lo * (hi / lo) ** (k / (n - 1)) for k in range(n)]
    out = []
    for k, f in enumerate(rods):
        t = 0.05 + SWEEP_SECONDS * (k / (n - 1)) ** 1.15 + rnd.uniform(-0.008, 0.008)
        swell = min(1.0, 0.5 + k / 6)                                # soft first touches
        taper = 1.0 - 0.55 * max(0.0, (k - n * 0.55) / (n * 0.45))   # top rods quieter
        tau = 1.2 * 1800.0 / f                                       # 1.2 s .. 0.33 s
        out.append((t, f, rnd.uniform(0.6, 0.95) * swell * taper, tau))
    return out


def ring(buf, start, f, amp, tau):
    """Add one struck note: a damped resonator per partial, y[i] = 2r cos(w) y[i-1] - r^2 y[i-2]."""
    sr, n = SAMPLE_RATE, len(buf)
    s0 = int(start * sr)
    for ratio, a in PARTIALS:
        fr = f * ratio
        if fr > MAX_PARTIAL_HZ:
            continue
        r = math.exp(-1.0 / (sr * tau / ratio ** 0.7))
        w = 2 * math.pi * fr / sr
        c1, c2 = 2 * r * math.cos(w), -r * r
        y1, y2 = amp * a * math.sin(w), 0.0
        limit = amp * a * 1e-3
        for i in range(s0, n):
            buf[i] += y1
            y1, y2 = c1 * y1 + c2 * y2, y1
            if abs(y1) < limit and abs(y2) < limit and i - s0 > sr // 10:
                break


def fade(buf, start, end):
    """Cosine fade from full volume at `start` to silence at `end` (seconds)."""
    f0, f1 = int(start * SAMPLE_RATE), min(int(end * SAMPLE_RATE), len(buf))
    for i in range(f0, len(buf)):
        buf[i] *= 0.5 * (1 + math.cos(math.pi * (i - f0) / (f1 - f0))) if i < f1 else 0.0


def synthesize():
    n = int(SAMPLE_RATE * CHIME_SECONDS)
    sweep, closing = [0.0] * n, [0.0] * n
    for start, f, amp, tau in strikes():
        ring(sweep, start, f, amp, tau)
    fade(sweep, *SWEEP_FADE)
    for start, f, amp, tau in CLOSING_NOTES:
        ring(closing, start, f, amp, tau)
    fade(closing, *END_FADE)
    buf = [a + b for a, b in zip(sweep, closing)]
    peak = max(abs(v) for v in buf)
    return struct.pack(f"<{n}h", *(int(v / peak * PEAK * 32767) for v in buf))


if __name__ == "__main__":
    pcm = synthesize()
    for path in (SND, WAV):
        os.makedirs(os.path.dirname(path), exist_ok=True)
    open(SND, "wb").write(pcm)
    with wave.open(WAV, "wb") as w:
        w.setnchannels(1), w.setsampwidth(2), w.setframerate(SAMPLE_RATE), w.writeframes(pcm)
    print(f"wrote {os.path.relpath(SND, ROOT)} ({len(pcm)} bytes) and {os.path.relpath(WAV, ROOT)}")
