"""Tiny BUSY Bar HTTP API client shared by the tools (Python 3 standard library only).

Device address and API key come from, in order:
  BUSYBAR_HOST / BUSYBAR_KEY environment variables,
  ~/.busybar_host / ~/.busybar_key files.
The key is the HTTP API access key (PIN) or an access token.
"""
import json
import os
import urllib.error
import urllib.request


def _setting(env, filename):
    value = os.environ.get(env)
    if value:
        return value.strip()
    path = os.path.expanduser(f"~/{filename}")
    if os.path.exists(path):
        return open(path).read().strip()
    raise SystemExit(f"set {env} or create {path}")


def host():
    return _setting("BUSYBAR_HOST", ".busybar_host")


def key():
    return _setting("BUSYBAR_KEY", ".busybar_key")


def api(method, path, body=None, raw=None, timeout=10):
    """Returns (HTTP status, response text); status 0 means the device was unreachable."""
    data = raw if raw is not None else (json.dumps(body).encode() if body is not None else None)
    ctype = "application/octet-stream" if raw is not None else "application/json"
    req = urllib.request.Request(f"http://{host()}{path}", data=data, method=method,
                                 headers={"X-API-Token": key(), "Content-Type": ctype})
    try:
        with urllib.request.urlopen(req, timeout=timeout) as r:
            return r.status, r.read().decode()
    except urllib.error.HTTPError as e:
        return e.code, e.read().decode()
    except OSError as e:
        return 0, str(e)
