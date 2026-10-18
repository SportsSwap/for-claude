"""`tra web`: start Sawnx on this laptop and open it in the browser."""

from __future__ import annotations

import secrets
import socket
import webbrowser
from typing import Callable

from flask import Flask
from werkzeug.serving import BaseWSGIServer, make_server

from ..settings import Settings

HOST = "127.0.0.1"
DEFAULT_PORT = 8766


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
        webbrowser.open(f"{address}?key={key}")
    else:
        echo(f"Open this address in your browser: {address}?key={key}")
    try:
        server.serve_forever()
    except KeyboardInterrupt:
        pass
    finally:
        server.server_close()
