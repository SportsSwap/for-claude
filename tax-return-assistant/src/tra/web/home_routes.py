"""Home (My Recent, My Starred), Documents, search, help, and actions on several documents at once."""

from __future__ import annotations

import io
import zipfile
from urllib.parse import urlencode

from flask import Flask, abort, flash, redirect, render_template, request, send_file

from ..privacy.guard import FileLockedError, SensitiveDataBlocked
from .client_names import load_names
from .messages import problem_text
from .routes import audit_for, settings
from .services.clients import list_clients
from .services.doclist import SORTS, all_documents, query, resolve
from .services.files import document_path, folder_names, move_document
from .stars import set_stars

FILTERS = ("q", "client", "year", "folder", "kind")


def _safe_next(url: str | None, default: str = "/") -> str:
    return url if url and url.startswith("/") and not url.startswith("//") else default


def doclist_context(rows, path: str, *, fixed: dict | None = None) -> dict:
    """Filter, sort and describe a document list for templates/_doclist.html."""
    args = {k: (request.args.get(k) or "").strip() for k in FILTERS}
    args.update(fixed or {})
    sort = request.args.get("sort") if request.args.get("sort") in SORTS else "changed"
    desc = request.args.get("dir", "desc" if sort == "changed" else "asc") == "desc"
    shown = query(rows, q=args["q"], client=args["client"], year=args["year"], folder=args["folder"],
                  kind=args["kind"], starred=request.args.get("tab") == "starred", sort=sort, desc=desc)

    def sort_url(column: str) -> str:
        params = {k: v for k, v in request.args.items() if k not in ("sort", "dir")}
        flip = "asc" if (column == sort and desc) else "desc" if column == sort else (
            "desc" if column == "changed" else "asc")
        return f"{path}?{urlencode({**params, 'sort': column, 'dir': flip})}"

    return {"rows": shown, "sort": sort, "desc": desc, "args": args, "sort_url": sort_url,
            "here": request.full_path.rstrip("?"),
            "clients": sorted({(r.code, r.client) for r in rows}, key=lambda c: c[1].lower()),
            "years": sorted({r.income_year for r in rows}, reverse=True),
            "folder_options": sorted({r.folder for r in rows}), "kinds": sorted({r.kind for r in rows})}


def _keys() -> list[str]:
    keys = request.form.getlist("key")
    if not keys:
        flash("Tick at least one document first.", "error")
    return keys


def register_home_routes(app: Flask) -> None:
    @app.get("/")
    def home():
        rows = all_documents(settings().tra_home)
        tab = "starred" if request.args.get("tab") == "starred" else "recent"
        return render_template("home.html", nav="home", tab=tab, starred_count=sum(r.starred for r in rows),
                               total=len(rows), **doclist_context(rows, "/"))

    @app.get("/documents")
    def documents_page():
        rows = all_documents(settings().tra_home)
        return render_template("documents.html", nav="documents", total=len(rows),
                               **doclist_context(rows, "/documents"))

    @app.get("/search")
    def search():
        q = (request.args.get("q") or "").strip()
        needle = q.lower()
        found = [c for c in list_clients(settings().tra_home)
                 if needle and (needle in (c.name or "").lower() or c.code.lower().startswith(needle))]
        rows = all_documents(settings().tra_home) if q else []
        return render_template("search.html", nav="", q=q, found_clients=found, total=len(rows),
                               **doclist_context(rows, "/search"))

    @app.get("/help")
    def help_page():
        return render_template("help.html", nav="help")

    @app.post("/stars")
    def stars():
        keys = _keys()
        if keys:
            try:
                for key in keys:
                    resolve(settings(), key)
                set_stars(settings().tra_home, keys, request.form.get("action") != "unstar")
            except ValueError as exc:
                abort(400, description=str(exc))
        return redirect(_safe_next(request.form.get("next")))

    @app.post("/download")
    def download():
        keys = _keys()
        if not keys:
            return redirect(_safe_next(request.form.get("next")))
        files = []
        try:
            for key in keys:
                ws, doc = resolve(settings(), key)
                path = document_path(ws, doc.doc_id)
                if path is None:
                    raise ValueError(f"{doc.filed_name} is filed in FYI; download it there.")
                files.append((path, doc.filed_name))
        except ValueError as exc:
            abort(400, description=str(exc))
        buffer = io.BytesIO()
        with zipfile.ZipFile(buffer, "w", zipfile.ZIP_DEFLATED) as zf:
            for path, name in files:
                zf.write(path, arcname=name)
        buffer.seek(0)
        return send_file(buffer, mimetype="application/zip", as_attachment=True, download_name="Sawnx documents.zip",
                         max_age=0)

    @app.post("/move")
    def move():
        keys = _keys()
        target = _safe_next(request.form.get("next"))
        if not keys:
            return redirect(target)
        folder = request.form.get("folder") or ""
        try:
            resolved = [resolve(settings(), k) for k in keys]
            if len({(ws.client_code, ws.income_year) for ws, _d in resolved}) != 1:
                raise ValueError("Documents can only be moved together when they belong to one client and year.")
            ws = resolved[0][0]
            if folder not in folder_names(ws):
                raise ValueError("Choose a folder that client has.")
            audit = audit_for(ws.client_code)
            for _ws, doc in resolved:
                move_document(ws, doc.doc_id, folder, audit)
        except (ValueError, SensitiveDataBlocked, FileLockedError, OSError) as exc:
            flash(problem_text(exc), "error")
        else:
            flash(f"{len(keys)} document{'' if len(keys) == 1 else 's'} moved to {folder}.", "ok")
        return redirect(target)

    @app.context_processor
    def _names():
        return {"client_names": load_names(settings().tra_home)}
