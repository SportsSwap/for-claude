"""A client's Rental page (docs/specs/2026-10-26-rental-properties-design.md)."""

from __future__ import annotations

from flask import Flask, flash, redirect, render_template, request

from ..privacy.guard import FileLockedError, SensitiveDataBlocked
from .client_routes import base_url, client_context
from .messages import problem_text
from .routes import audit_for, settings
from .services.clients import workspace_for
from .services.rental import add_property, remove_property, rental_page, save_property, set_columns, set_documents

PROBLEMS = (ValueError, SensitiveDataBlocked, FileLockedError, OSError)


def register_rental_routes(app: Flask) -> None:
    @app.get("/c/<code>/<int:fy>/rental")
    def client_rental(code: str, fy: int):
        ws = workspace_for(settings(), code, fy)
        return render_template("client_rental.html", **client_context(ws, "rental"), **rental_page(ws))

    def _change(code: str, fy: int, action, done: str):
        ws = workspace_for(settings(), code, fy)
        try:
            result = action(ws, audit_for(code))
        except PROBLEMS as exc:
            flash(problem_text(exc), "error")
        else:
            flash(done if not callable(done) else done(result), "ok")
        return redirect(f"{base_url(ws)}/rental")

    @app.post("/c/<code>/<int:fy>/rental/add")
    def rental_add(code: str, fy: int):
        return _change(code, fy, lambda ws, audit: add_property(ws, request.form.get("name", ""), audit),
                       lambda p: f"{p.name} added. Set its share and private use below.")

    @app.post("/c/<code>/<int:fy>/rental/documents")
    def rental_documents(code: str, fy: int):
        return _change(code, fy, lambda ws, audit: set_documents(ws, request.form, audit),
                       lambda n: f"{n} document{'' if n == 1 else 's'} moved." if n else "Nothing changed.")

    @app.post("/c/<code>/<int:fy>/rental/columns")
    def rental_columns(code: str, fy: int):
        return _change(code, fy, lambda ws, audit: set_columns(ws, request.form, audit),
                       lambda n: f"{n} figure{'' if n == 1 else 's'} moved." if n else "Nothing changed.")

    @app.post("/c/<code>/<int:fy>/rental/<pid>")
    def rental_save(code: str, fy: int, pid: str):
        return _change(code, fy, lambda ws, audit: save_property(ws, pid, request.form, audit),
                       lambda p: f"{p.name} saved. It's used the next time you prepare the return.")

    @app.post("/c/<code>/<int:fy>/rental/<pid>/remove")
    def rental_remove(code: str, fy: int, pid: str):
        return _change(code, fy, lambda ws, audit: remove_property(ws, pid, audit), "Property removed.")
