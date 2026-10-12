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
import threading
import time
import urllib.request

TITLE = "Rocket Engine Sizing Tool"

# FROZEN: running as a packaged, double-click app (built with PyInstaller)
# rather than as a Python script. Then the program files live inside the app
# bundle (sys._MEIPASS) and there is no separate Python to start the server
# with, so the app starts a second copy of itself with --serve instead.
FROZEN = getattr(sys, "frozen", False)
HERE = getattr(sys, "_MEIPASS", os.path.dirname(os.path.abspath(__file__)))


def server_options(port):
    return ["--server.headless", "true",
            "--server.address", "127.0.0.1",
            "--server.port", str(port),
            "--server.fileWatcherType", "none",
            "--browser.gatherUsageStats", "false",
            "--global.developmentMode", "false"]


def server_command(port):
    """The command that starts the Streamlit server on this port. The server
    runs as a second copy of this program in --serve mode."""
    me = [sys.executable] if FROZEN else [sys.executable, os.path.abspath(__file__)]
    return [*me, "--serve", str(port), "--watch-parent"]


def exit_with_parent():
    """Lifeline: the window process keeps a pipe open to this process's input.
    However the window process ends (closed, quit, crashed), the system closes
    the pipe, the read below returns nothing, and the server shuts down."""
    try:
        while os.read(0, 1024):
            pass
    except OSError:
        pass
    os._exit(0)


def serve(port, watch_parent=False):
    """Run the Streamlit server inside this process."""
    if watch_parent:
        threading.Thread(target=exit_with_parent, daemon=True).start()
    from streamlit.web import cli as stcli
    sys.argv = ["streamlit", "run", os.path.join(HERE, "app.py"),
                *server_options(port)]
    sys.exit(stcli.main())


def log_path():
    """Where app.log goes. A packaged app can't write inside itself (that
    would break its signature), so it logs to the user's own folders."""
    if not FROZEN:
        return os.path.join(HERE, "app.log")
    if sys.platform == "darwin":
        folder = os.path.expanduser("~/Library/Logs/Rocket Engine Sizing Tool")
    elif os.name == "nt":
        folder = os.path.join(os.environ.get("LOCALAPPDATA", os.path.expanduser("~")),
                              "Rocket Engine Sizing Tool")
    else:
        folder = os.path.expanduser("~/.rocket-engine-sizing-tool")
    os.makedirs(folder, exist_ok=True)
    return os.path.join(folder, "app.log")

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
    if len(sys.argv) >= 3 and sys.argv[1] == "--serve":
        serve(sys.argv[2], watch_parent="--watch-parent" in sys.argv)
        return

    import webview   # only the window process needs it

    port = free_port()
    url = f"http://127.0.0.1:{port}"

    # Without a console (pythonw on Windows, or the packaged app), send the
    # server's messages to app.log. The Mac script launcher already
    # redirects everything to app.log itself.
    log = None
    if FROZEN or sys.stdout is None:
        log = open(log_path(), "a", encoding="utf-8")

    server = subprocess.Popen(
        server_command(port),
        cwd=HERE,
        stdin=subprocess.PIPE,      # the server's lifeline (see exit_with_parent)
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
                "COULD NOT START. DETAILS: " + log_path().replace("&", "&amp;").replace("<", "&lt;")))

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
