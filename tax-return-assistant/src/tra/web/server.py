"""`tra web`: start Sawnx on this laptop and open it in its own app-style window (Chrome, else Edge)."""

from __future__ import annotations

import os
import secrets
import socket
import subprocess
import webbrowser
from typing import Callable

from flask import Flask
from werkzeug.serving import BaseWSGIServer, make_server

from ..settings import Settings

HOST = "127.0.0.1"
DEFAULT_PORT = 8766

# Where Chrome and Edge install on Windows, in the order tried: Chrome first (the owner's choice), then Edge.
# "--app=" opens a window of its own, without tabs or an address bar.
APP_BROWSERS = (
    ("ProgramFiles", r"Google\Chrome\Application\chrome.exe"),
    ("ProgramFiles(x86)", r"Google\Chrome\Application\chrome.exe"),
    ("LOCALAPPDATA", r"Google\Chrome\Application\chrome.exe"),
    ("ProgramFiles(x86)", r"Microsoft\Edge\Application\msedge.exe"),
    ("ProgramFiles", r"Microsoft\Edge\Application\msedge.exe"),
)


def app_window_command(url: str, *, env=None, exists=os.path.isfile, join=os.path.join) -> list[str] | None:
    """The command that opens ``url`` in a Chrome (or Edge) app window, or None if neither is installed."""
    env = os.environ if env is None else env
    for variable, relative in APP_BROWSERS:
        base = env.get(variable)
        if base and exists(join(base, relative)):
            return [join(base, relative), f"--app={url}"]
    return None


def open_in_browser(url: str, *, env=None, exists=os.path.isfile, launch=subprocess.Popen,
                    join=os.path.join) -> None:
    """A Chrome or Edge app window if one can be started, otherwise the default browser."""
    command = app_window_command(url, env=env, exists=exists, join=join)
    if command:
        try:
            launch(command)
            return
        except OSError:
            pass
    webbrowser.open(url)


def make_session_key() -> str:
    return secrets.token_urlsafe(32)


def _port_free(port: int) -> bool:
    probe = socket.socket()
    try:
        if hasattr(socket, "SO_EXCLUSIVEADDRUSE"):  # Windows: don't share a port another program holds
            probe.setsockopt(socket.SOL_SOCKET, socket.SO_EXCLUSIVEADDRUSE, 1)
        probe.bind((HOST, port))
        return True
    except OSError:
        return False
    finally:
        probe.close()


def bind(app: Flask, port: int) -> BaseWSGIServer:
    """Listen on 127.0.0.1 only. If the port is taken (Sawnx already open?), use any free one.

    werkzeug exits the process when it can't bind, so the port is checked first.
    """
    return make_server(HOST, port if port and _port_free(port) else 0, app, threaded=True)


def run(settings: Settings, *, port: int = DEFAULT_PORT, open_browser: bool = True,
        echo: Callable[[str], None] = print) -> None:
    from . import create_app

    key = make_session_key()
    app = create_app(settings, key, port)
    server = bind(app, port)
    app.config["SAWNX"]["port"] = server.server_port
    address = f"http://{HOST}:{server.server_port}/"
    echo(f"Sawnx is running at {address}  Close this window to stop it.")
    if open_browser:
        open_in_browser(f"{address}?key={key}")
    else:
        echo(f"Open this address in your browser: {address}?key={key}")
    try:
        server.serve_forever()
    except KeyboardInterrupt:
        pass
    finally:
        server.server_close()
