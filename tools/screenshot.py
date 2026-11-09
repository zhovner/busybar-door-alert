#!/usr/bin/env python3
"""Save the BUSY Bar front display (72x16) as an upscaled PNG.

  python3 tools/screenshot.py out.png [scale]     (default scale 10)
"""
import base64
import os
import struct
import sys
import zlib

sys.path.insert(0, os.path.dirname(os.path.abspath(__file__)))
import busybar  # noqa: E402

W, H = 72, 16


def grab():
    status, text = busybar.api("GET", "/api/screen?display=0")
    if status != 200:
        raise SystemExit(f"screen: HTTP {status} {text}")
    raw = base64.b64decode(text)
    # the device returns BGR; swap to RGB
    return b"".join(raw[i:i + 3][::-1] for i in range(0, len(raw), 3))


def png(path, rgb, scale):
    rows = b""
    for y in range(H):
        line = b"".join(rgb[(y * W + x) * 3:(y * W + x) * 3 + 3] * scale for x in range(W))
        rows += (b"\0" + line) * scale
    chunk = lambda t, d: struct.pack(">I", len(d)) + t + d + struct.pack(">I", zlib.crc32(t + d) & 0xFFFFFFFF)
    with open(path, "wb") as f:
        f.write(b"\x89PNG\r\n\x1a\n" + chunk(b"IHDR", struct.pack(">IIBBBBB", W * scale, H * scale, 8, 2, 0, 0, 0))
                + chunk(b"IDAT", zlib.compress(rows)) + chunk(b"IEND", b""))


if __name__ == "__main__":
    png(sys.argv[1], grab(), int(sys.argv[2]) if len(sys.argv) > 2 else 10)
