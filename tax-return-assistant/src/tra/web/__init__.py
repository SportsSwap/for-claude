"""Sawnx: a local web front end for the tool. It runs on 127.0.0.1 only and never lodges anything.

Routes are thin; the behaviour is in the service modules, which call the same
code the `tra` commands use. See docs/specs/2026-10-18-sawnx-design.md.
"""

from __future__ import annotations

import logging
import secrets

from flask import Flask, render_template, request
from werkzeug.exceptions import HTTPException

from ..money import format_dollars
from ..privacy.logging_filter import configure_logging
from ..settings import Settings
from .security import install_security

MAX_UPLOAD = 50 * 1024 * 1024
log = logging.getLogger("tra.web")

ERROR_TEXT = {
    403: ("Not allowed", "Open Sawnx from its shortcut on this laptop."),
    404: ("Not found", "That page or document doesn't exist. Go back to the client list and try again."),
    405: ("Not allowed", "That action isn't available here."),
    413: ("File too big", "That file is over 50 MB. Split it, or file it in FYI directly."),
}


def estimate_text(net) -> str:
    if net is None:
        return "–"
    return f"{'Payable' if net >= 0 else 'Refund'} {format_dollars(abs(net))}"


def create_app(settings: Settings, session_key: str, port: int, *, ai_client=None) -> Flask:
    """``ai_client`` replaces the Anthropic client in tests; the AI reader stays off unless switched on."""
    app = Flask(__name__)
    app.secret_key = session_key
    app.config["MAX_CONTENT_LENGTH"] = MAX_UPLOAD
    app.config["SAWNX"] = {"settings": settings, "port": port, "ai_client": ai_client}
    configure_logging(settings.tra_home / "logs" / "tra.log")
    install_security(app, session_key)
    app.add_template_filter(format_dollars, "money")
    app.add_template_filter(estimate_text, "estimate")

    from .context import register_context
    from .routes import register

    register_context(app)
    register(app)

    @app.errorhandler(HTTPException)
    def http_error(exc: HTTPException):
        title, text = ERROR_TEXT.get(exc.code or 500, ("Something went wrong", exc.description or ""))
        return render_template("error.html", code=exc.code, title=title, text=text, reference=None), exc.code

    @app.errorhandler(Exception)
    def unexpected(exc: Exception):
        reference = secrets.token_hex(3).upper()
        log.error("Unexpected error %s on %s: %s: %s", reference, request.path, type(exc).__name__, exc)
        return render_template("error.html", code=500, title="Something went wrong",
                               text="Sawnx hit an unexpected problem. Nothing was lodged. Try again, and if it keeps "
                                    "happening, give whoever maintains the tool this reference.",
                               reference=reference), 500

    return app
