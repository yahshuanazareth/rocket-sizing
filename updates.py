"""
updates.py - checks GitHub for a newer release of the program.

The check runs in the background as soon as the app starts, so it never
slows down loading. If there is no internet, or anything else goes wrong,
it stays quiet and the app works as normal.
"""

import json
import re
import ssl
import threading
import urllib.request

from version import REPO, VERSION

_result = {"done": False, "latest": None, "url": None}
_lock = threading.Lock()
_started = False


def _numbers(version):
    """'v1.10.2' -> (1, 10, 2), so versions compare as numbers, not text."""
    return tuple(int(n) for n in re.findall(r"\d+", version))


def _ssl_context():
    # Some Python installs on macOS have no certificate list of their own;
    # certifi (installed alongside Streamlit) provides one.
    try:
        import certifi
        return ssl.create_default_context(cafile=certifi.where())
    except Exception:
        return ssl.create_default_context()


def _check():
    try:
        req = urllib.request.Request(
            f"https://api.github.com/repos/{REPO}/releases/latest",
            headers={"Accept": "application/vnd.github+json",
                     "User-Agent": "rocket-engine-sizing-tool"})
        with urllib.request.urlopen(req, timeout=6, context=_ssl_context()) as r:
            data = json.load(r)
        tag = data.get("tag_name", "")
        if _numbers(tag) > _numbers(VERSION):
            _result["latest"] = tag.lstrip("vV")
            _result["url"] = data.get("html_url")
    except Exception:
        pass   # offline, rate-limited, no releases yet: just skip the notice
    finally:
        _result["done"] = True


def start():
    """Start the background check (only once per run of the program)."""
    global _started
    with _lock:
        if not _started:
            _started = True
            threading.Thread(target=_check, daemon=True).start()


def available():
    """(newest version, its download page) if an update is out, else None."""
    if _result["latest"]:
        return _result["latest"], _result["url"]
    return None
