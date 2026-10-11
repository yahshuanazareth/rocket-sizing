"""
desktop.py - runs the Rocket Engine Sizing Tool as its own desktop window.

How it works:
  1. Starts the app (app.py) as a small server that only this computer can
     reach (address 127.0.0.1). Nothing goes on the internet.
  2. Opens a native window that shows it, instead of a browser tab.
  3. Shuts the server down when you close the window.

Run it with:   python desktop.py
or double-click "Rocket Engine Sizing Tool.app" (Mac)
or "Start Rocket Sizing Tool (Windows).bat" (Windows).
"""

import os
import socket
import subprocess
import sys
import time
import urllib.request

import webview

HERE = os.path.dirname(os.path.abspath(__file__))
TITLE = "Rocket Engine Sizing Tool"

LOADING_PAGE = """
<html><body style="margin:0;height:100vh;display:flex;align-items:center;
justify-content:center;background:#0b3866;color:#fff;font-family:Menlo,monospace;
background-image:linear-gradient(rgba(255,255,255,.05) 1px,transparent 1px),
linear-gradient(90deg,rgba(255,255,255,.05) 1px,transparent 1px);
background-size:24px 24px;">
<div style="text-align:center;letter-spacing:.12em">
<div style="font-size:26px;font-weight:bold">ROCKET ENGINE SIZING TOOL</div>
<div style="margin-top:14px;color:#cfe3ff;font-size:13px">LOADING NASA CEA&hellip;</div>
</div></body></html>
"""


def free_port():
    """Ask the operating system for an unused port number."""
    with socket.socket() as s:
        s.bind(("127.0.0.1", 0))
        return s.getsockname()[1]


def wait_until_ready(url, timeout=90):
    """Poll the server's health check until it answers, or give up."""
    end = time.time() + timeout
    while time.time() < end:
        try:
            with urllib.request.urlopen(url + "/_stcore/health", timeout=2):
                return True
        except Exception:
            time.sleep(0.4)
    return False


def main():
    port = free_port()
    url = f"http://127.0.0.1:{port}"

    # On Windows the launcher starts this file with pythonw.exe, which has no
    # console, so send the server's messages to app.log instead. The Mac
    # launcher already redirects everything to app.log itself.
    log = None
    if sys.stdout is None:
        log = open(os.path.join(HERE, "app.log"), "a", encoding="utf-8")

    server = subprocess.Popen(
        [sys.executable, "-m", "streamlit", "run", os.path.join(HERE, "app.py"),
         "--server.headless", "true",
         "--server.address", "127.0.0.1",
         "--server.port", str(port),
         "--global.developmentMode", "false"],
        cwd=HERE,
        stdout=log,
        stderr=log,
        # Windows: don't pop up a console window for the server
        creationflags=getattr(subprocess, "CREATE_NO_WINDOW", 0),
    )

    webview.settings["ALLOW_DOWNLOADS"] = True   # lets the download buttons save files
    window = webview.create_window(
        TITLE, html=LOADING_PAGE, width=1440, height=920, min_size=(1000, 680),
        background_color="#0b3866", text_select=True)

    def load_app():
        if wait_until_ready(url):
            window.load_url(url)
        else:
            window.load_html(LOADING_PAGE.replace(
                "LOADING NASA CEA&hellip;",
                "COULD NOT START. SEE app.log IN THE PROJECT FOLDER."))

    try:
        webview.start(load_app)
    finally:
        server.terminate()
        try:
            server.wait(timeout=5)
        except subprocess.TimeoutExpired:
            server.kill()
        if log:
            log.close()


if __name__ == "__main__":
    main()
