#!/usr/bin/env python3
"""Package src/ into dist/<app_id>.tgz and optionally install / start it on the BUSY Bar.

  python3 tools/build.py              build only
  python3 tools/build.py --install    build, then stage + install over the HTTP API
  python3 tools/build.py --install --run

The archive holds everything under a top-level folder named after the manifest id
(the device requires the root directory name to equal the id).
"""
import json
import os
import sys
import tarfile

ROOT = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))
SRC = os.path.join(ROOT, "src")
sys.path.insert(0, os.path.dirname(os.path.abspath(__file__)))


def build():
    app_id = json.load(open(os.path.join(SRC, "appmeta", "manifest.json")))["id"]
    out = os.path.join(ROOT, "dist", f"{app_id}.tgz")
    os.makedirs(os.path.dirname(out), exist_ok=True)
    with tarfile.open(out, "w:gz", format=tarfile.USTAR_FORMAT) as tar:
        tar.add(SRC, arcname=app_id, filter=lambda ti: None if ti.name.endswith((".wav", ".DS_Store")) else ti)
    print(f"built {os.path.relpath(out, ROOT)} ({os.path.getsize(out)} bytes)")
    return app_id, out


def install(app_id, path):
    import busybar
    status, text = busybar.api("POST", "/api/apps/stage", raw=open(path, "rb").read(), timeout=60)
    print("stage:", status, text.strip())
    if status != 200:
        sys.exit(1)
    install_key = json.loads(text)["install_key"]
    status, text = busybar.api("POST", f"/api/apps/install?install_key={install_key}")
    print("install:", status, text.strip())
    if status != 200:
        sys.exit(1)


if __name__ == "__main__":
    app_id, path = build()
    if "--install" in sys.argv:
        install(app_id, path)
    if "--run" in sys.argv:
        import busybar
        print("run:", *busybar.api("POST", f"/api/apps/launch?app_id={app_id}"))
