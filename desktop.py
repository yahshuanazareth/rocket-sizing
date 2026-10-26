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

import json
import os
import shutil
import socket
import subprocess
import sys
import threading
import time
import urllib.request

import splash

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
    # Load the heavy math libraries now, on the main thread. On Windows,
    # numpy can freeze forever if its first import happens on the background
    # thread Streamlit runs app.py on (it hung at 20% on the loading screen).
    import numpy  # noqa: F401
    import pandas  # noqa: F401
    import matplotlib
    matplotlib.use("Agg")
    import matplotlib.pyplot  # noqa: F401
    import engine  # noqa: F401  (loads NASA CEA)
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




def unblock_downloaded_files():
    """Windows tags every file unzipped from an internet download as "came
    from another computer" (a hidden Zone.Identifier mark). .NET, which draws
    the window on Windows, then refuses to load its DLLs and the app crashes
    with "Failed to resolve Python.Runtime.Loader.Initialize". Removing the
    mark from this program's own DLLs is the same as ticking "Unblock" in
    each file's Properties."""
    if os.name != "nt" or not FROZEN:
        return
    for root, _dirs, files in os.walk(HERE):
        for name in files:
            if name.lower().endswith(".dll"):
                try:
                    os.remove(os.path.join(root, name) + ":Zone.Identifier")
                except OSError:
                    pass   # not marked, or no permission: nothing to do


def selftest(out_path):
    """Used by the build on GitHub: runs the whole calculation once with the
    default design and writes the result to out_path, so a download that
    can't calculate is caught before anyone gets it."""
    import traceback
    try:
        import engine
        res = engine.size_engine(engine.Inputs())
        import matplotlib
        matplotlib.use("Agg")
        import matplotlib.pyplot  # noqa: F401
        import splash, updates, version  # noqa: F401,E401
        msg, code = f"SELFTEST OK  Isp_vac={res.Isp_vac:.1f} s  Dt={res.Dt:.3f} in", 0
    except BaseException:
        msg, code = "SELFTEST FAILED\n" + traceback.format_exc(), 1
    with open(out_path, "w", encoding="utf-8") as f:
        f.write(msg + "\n")
    sys.exit(code)


def update_from_git():
    """For copies downloaded with git: get the newest version from GitHub
    before starting. "--ff-only" only ever moves forward to GitHub's version,
    so it never overwrites changes made in this folder; if anything stands in
    the way (no internet, local edits, no git) it skips the update quietly."""
    if FROZEN or not os.path.isdir(os.path.join(HERE, ".git")) or not shutil.which("git"):
        return
    req = os.path.join(HERE, "requirements.txt")

    def read(path):
        try:
            with open(path, encoding="utf-8") as f:
                return f.read()
        except OSError:
            return ""

    before = read(req)
    try:
        r = subprocess.run(
            ["git", "pull", "--ff-only", "--quiet"], cwd=HERE, timeout=20,
            capture_output=True, text=True, stdin=subprocess.DEVNULL,
            env={**os.environ, "GIT_TERMINAL_PROMPT": "0"},   # never ask for a password
            creationflags=getattr(subprocess, "CREATE_NO_WINDOW", 0))
    except Exception as err:
        print("Update check skipped:", err)
        return
    if r.returncode != 0:
        print("Update skipped:", (r.stderr or r.stdout).strip())
        return
    # The update added a library: install it before the app needs it.
    if read(req) != before:
        subprocess.run([sys.executable, "-m", "pip", "install", "-r", req], cwd=HERE,
                       creationflags=getattr(subprocess, "CREATE_NO_WINDOW", 0))


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
    if len(sys.argv) >= 3 and sys.argv[1] == "--selftest":
        selftest(sys.argv[2])
        return

    unblock_downloaded_files()   # must run before webview loads its DLLs
    import webview   # only the window process needs it

    port = free_port()
    url = f"http://127.0.0.1:{port}"

    # Without a console (pythonw on Windows, or the packaged app), send the
    # server's messages to app.log. The Mac script launcher already
    # redirects everything to app.log itself.
    log = None
    if FROZEN or sys.stdout is None:
        log = open(log_path(), "a", encoding="utf-8")

    webview.settings["ALLOW_DOWNLOADS"] = True   # lets the download buttons save files
    window = webview.create_window(
        TITLE, html=splash.splash_page(0), width=1440, height=920, min_size=(1000, 680),
        background_color="#0b3866", text_select=True)

    server = []
    closed = []
    window.events.closed += lambda: closed.append(True)

    def load_app():
        # Runs once the window is open, so the loading screen shows meanwhile.
        update_from_git()
        server.append(subprocess.Popen(
            server_command(port),
            cwd=HERE,
            stdin=subprocess.PIPE,      # the server's lifeline (see exit_with_parent)
            stdout=log,
            stderr=log,
            # Windows: don't pop up a console window for the server
            creationflags=getattr(subprocess, "CREATE_NO_WINDOW", 0),
        ))
        if wait_until_ready(url):
            # Server is up: tick off the first step on the page already showing.
            # (Updating it in place, rather than loading a second page, keeps
            # it from racing with the app page below.)
            window.evaluate_js("document.body.innerHTML = "
                               + json.dumps(splash.splash_html(1)))
            window.load_url(url)
            # If the server stops while the window is open, say so instead of
            # leaving the loading screen up forever.
            code = server[0].wait()
            print(f"Server stopped with exit code {code}", flush=True)
            if closed:
                return   # normal: the user closed the window
            try:
                window.load_html(splash.splash_page(0, error=(
                    f"The engine server stopped unexpectedly (code {code}). Details: "
                    + log_path().replace("&", "&amp;").replace("<", "&lt;"))))
            except Exception:
                pass   # the window was already closed
        else:
            window.load_html(splash.splash_page(0, error=(
                "Could not start. Details: "
                + log_path().replace("&", "&amp;").replace("<", "&lt;"))))

    try:
        webview.start(load_app)
    finally:
        for proc in server:
            proc.terminate()
            try:
                proc.wait(timeout=5)
            except subprocess.TimeoutExpired:
                proc.kill()
        if log:
            log.close()


if __name__ == "__main__":
    try:
        main()
    except Exception:
        # Without a console the error would only appear in a popup; keep a
        # copy in app.log so it can be sent to the developer.
        import traceback
        try:
            with open(log_path(), "a", encoding="utf-8") as f:
                f.write("The app crashed:\n" + traceback.format_exc())
        except Exception:
            pass
        raise
