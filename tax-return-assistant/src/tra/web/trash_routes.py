"""Delete a document, Deleted items, Restore and Delete forever. The behaviour is in tra/trash.py."""

from __future__ import annotations

import getpass

from flask import Flask, flash, redirect, render_template, request

from ..privacy.guard import FileLockedError, SensitiveDataBlocked
from ..trash import delete_document, deleted_documents, purge_document, restore_document
from .client_routes import base_url, cab_q, client_context, space_of
from .home_routes import _keys, _safe_next
from .messages import problem_text
from .routes import audit_for, settings
from .services.clients import workspace_for
from .services.doclist import resolve

PROBLEMS = (ValueError, SensitiveDataBlocked, FileLockedError, OSError)


def _figures_text(n: int, verb: str) -> str:
    return f" Its {n} figure{'' if n == 1 else 's'} {verb} the return; prepare again." if n else ""


def register_trash_routes(app: Flask) -> None:
    def _urls(code: str, fy: int):
        ws = workspace_for(settings(), code, fy)
        space = space_of(ws)
        q = cab_q(space).rstrip("&")
        return ws, space, f"{base_url(ws)}/files{'?' + q if q else ''}", f"{base_url(ws)}/deleted{'?' + q if q else ''}"

    @app.post("/c/<code>/<int:fy>/doc/<doc_id>/delete")
    def doc_delete(code: str, fy: int, doc_id: str):
        _ws, space, files_url, _deleted_url = _urls(code, fy)
        try:
            n = delete_document(space, doc_id, getpass.getuser(), audit_for(code))
        except PROBLEMS as exc:
            flash(problem_text(exc), "error")
        else:
            flash(f"{doc_id} moved to Deleted items.{_figures_text(n, 'came out of')}", "ok")
        return redirect(files_url)

    @app.post("/delete")
    def bulk_delete():
        keys = _keys()
        target = _safe_next(request.form.get("next"))
        if not keys:
            return redirect(target)
        done = 0
        try:
            for key in keys:
                space, doc = resolve(settings(), key)
                delete_document(space, doc.doc_id, getpass.getuser(), audit_for(space.client_code))
                done += 1
        except PROBLEMS as exc:
            flash(problem_text(exc) + (f" ({done} deleted before that.)" if done else ""), "error")
        else:
            flash(f"{done} document{'' if done == 1 else 's'} deleted. Restore them from Deleted items.", "ok")
        return redirect(target)

    @app.get("/c/<code>/<int:fy>/deleted")
    def deleted(code: str, fy: int):
        ws, space, files_url, _deleted_url = _urls(code, fy)
        return render_template("client_deleted.html", **client_context(ws, "files"), items=deleted_documents(space),
                               cab=getattr(space, "code", ""), cabinet=getattr(space, "cabinet", "Tax return"),
                               files_url=files_url)

    @app.post("/c/<code>/<int:fy>/deleted/<doc_id>/restore")
    def deleted_restore(code: str, fy: int, doc_id: str):
        _ws, space, files_url, deleted_url = _urls(code, fy)
        try:
            n = restore_document(space, doc_id, getpass.getuser(), audit_for(code))
        except PROBLEMS as exc:
            flash(problem_text(exc), "error")
            return redirect(deleted_url)
        flash(f"{doc_id} restored.{_figures_text(n, 'are back in')}", "ok")
        return redirect(files_url)

    @app.post("/c/<code>/<int:fy>/deleted/<doc_id>/forever")
    def deleted_forever(code: str, fy: int, doc_id: str):
        _ws, space, _files_url, deleted_url = _urls(code, fy)
        try:
            purge_document(space, doc_id, audit_for(code))
        except PROBLEMS as exc:
            flash(problem_text(exc), "error")
        else:
            flash(f"{doc_id} deleted forever.", "ok")
        return redirect(deleted_url)
