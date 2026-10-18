"""A client's pages: Files, Figures, Prepare, Review notes, Notes."""

from __future__ import annotations

import getpass
import mimetypes
import os

from flask import Flask, abort, current_app, flash, redirect, render_template, request, send_file

from ..ingest.classify import load_doc_types
from ..filing.fyi_store import make_store
from ..ingest.extractors.ai_reader import AiReaderUnavailable, ai_reader_from_settings
from ..privacy.guard import FileLockedError, SensitiveDataBlocked
from ..checks import load_citations
from ..review_store import load_review, mark_reviewed, note_key, save_response
from ..run import PrepareError
from ..taxcalc.rates import RatesError
from ..workpaper.build import citation_text
from ..workspace import Workspace
from .client_notes import add_note, delete_note, edit_note, list_notes
from .messages import problem_text
from .routes import audit_for, settings
from .services.clients import workspace_for
from .services.files import add_folder, document_path, documents, find_document, folder_names, folders, move_document
from .services.figures import FiguresFileProblem, add_figure, figure_rows, label_choices, set_figure
from .services.imports import RETURN_TYPES, import_file
from .services.activity import activity
from .services.prepare import COMPONENTS, load_summary, run_prepare, workpapers
from .status import job_status

INLINE_TYPES = {"application/pdf", "image/png", "image/jpeg"}


def client_context(ws: Workspace, tab: str) -> dict:
    return {"client": {"code": ws.client_code, "fy": ws.income_year, "status": job_status(ws), "tab": tab},
            "nav": "clients"}


def base_url(ws: Workspace) -> str:
    return f"/c/{ws.client_code}/{ws.income_year}"


def render_files(ws: Workspace, folder: str | None, view_id: str = "", results=None, status: int = 200):
    names = folder_names(ws)
    folder = folder if folder in names else None
    return render_template("client_files.html", **client_context(ws, "files"), folders=folders(ws), folder=folder,
                           docs=documents(ws, folder), view=find_document(ws, view_id), folder_names=names,
                           doc_types=load_doc_types(), results=results, return_types=RETURN_TYPES), status


def register_client_routes(app: Flask) -> None:
    @app.get("/c/<code>/<int:fy>/files")
    def files(code: str, fy: int):
        ws = workspace_for(settings(), code, fy)
        return render_files(ws, request.args.get("folder"), request.args.get("view", ""))

    @app.post("/c/<code>/<int:fy>/folders")
    def folder_add(code: str, fy: int):
        ws = workspace_for(settings(), code, fy)
        name = (request.form.get("name") or "").strip()
        try:
            add_folder(ws, name, audit_for(code))
        except (ValueError, SensitiveDataBlocked, OSError) as exc:
            flash(problem_text(exc), "error")
            return redirect(f"{base_url(ws)}/files")
        flash(f"Folder {name} added.", "ok")
        return redirect(f"{base_url(ws)}/files?folder={name}")

    @app.get("/c/<code>/<int:fy>/doc/<doc_id>")
    def doc_view(code: str, fy: int, doc_id: str):
        ws = workspace_for(settings(), code, fy)
        doc = find_document(ws, doc_id)
        if doc is None:
            abort(404)
        path = document_path(ws, doc_id)
        if path is None:
            return render_template("error.html", title="Filed in FYI", text=f"{doc.filed_name} is filed in FYI. "
                                   "Open it there.", reference=None, nav="clients")
        mimetype = mimetypes.guess_type(path.name)[0] or "application/octet-stream"
        return send_file(path, mimetype=mimetype, as_attachment=mimetype not in INLINE_TYPES,
                         download_name=doc.filed_name, max_age=0)

    @app.post("/c/<code>/<int:fy>/doc/<doc_id>/move")
    def doc_move(code: str, fy: int, doc_id: str):
        ws = workspace_for(settings(), code, fy)
        folder = request.form.get("folder") or ""
        try:
            moved = move_document(ws, doc_id, folder, audit_for(code))
        except (ValueError, SensitiveDataBlocked, FileLockedError, OSError) as exc:
            flash(problem_text(exc), "error")
            return redirect(f"{base_url(ws)}/files?view={doc_id}")
        flash(f"{moved.filed_name} moved to {folder}.", "ok")
        return redirect(f"{base_url(ws)}/files?folder={folder}&view={doc_id}")

    @app.post("/c/<code>/<int:fy>/import")
    def import_docs(code: str, fy: int):
        ws = workspace_for(settings(), code, fy)
        uploads = [u for u in request.files.getlist("files") if u and u.filename]
        if not uploads:
            flash("Choose at least one file to import.", "error")
            return redirect(f"{base_url(ws)}/files")
        store = make_store(settings(), warn=lambda message: flash(message, "error"))
        doc_types, audit = load_doc_types(), audit_for(code)
        return_type = request.form.get("return_type") or "individual"
        try:
            ai_reader = ai_reader_from_settings(settings().tra_home, os.environ,
                                                client=current_app.config["SAWNX"]["ai_client"])
        except AiReaderUnavailable as exc:
            flash(str(exc), "error")
            ai_reader = None
        results = [import_file(ws, store, doc_types, audit, upload, mode=request.form.get(f"mode_{i}") or "read",
                               folder=request.form.get(f"folder_{i}") or None, return_type=return_type,
                               position=i + 1, ai_reader=ai_reader)
                   for i, upload in enumerate(uploads)]
        return render_files(ws, None, results=results)

    @app.get("/c/<code>/<int:fy>/notes")
    def notes(code: str, fy: int):
        ws = workspace_for(settings(), code, fy)
        return render_template("client_notes.html", **client_context(ws, "notes"),
                               notes=list_notes(settings().tra_home, code), activity=activity(ws))

    def _notes_action(code: str, action):
        try:
            fy = int(request.form.get("fy") or 0)
        except ValueError:
            fy = 0
        ws = workspace_for(settings(), code, fy)
        audit_for(code)
        try:
            action(ws)
        except (ValueError, SensitiveDataBlocked, FileLockedError, OSError) as exc:
            flash(problem_text(exc), "error")
        return redirect(f"{base_url(ws)}/notes")

    @app.post("/c/<code>/notes")
    def note_add(code: str):
        return _notes_action(code, lambda ws: add_note(settings().tra_home, code, request.form.get("text", ""),
                                                       getpass.getuser(), ws.income_year))

    @app.post("/c/<code>/notes/<note_id>/edit")
    def note_edit(code: str, note_id: str):
        return _notes_action(code, lambda ws: edit_note(settings().tra_home, code, note_id,
                                                        request.form.get("text", "")))

    @app.post("/c/<code>/notes/<note_id>/delete")
    def note_delete(code: str, note_id: str):
        return _notes_action(code, lambda ws: delete_note(settings().tra_home, code, note_id))

    def _figures_problem(exc: BaseException) -> str:
        if isinstance(exc, FileLockedError):
            return "figures.csv is open in Excel. Close it and try again."
        return problem_text(exc)

    @app.get("/c/<code>/<int:fy>/figures")
    def figures_tab(code: str, fy: int):
        ws = workspace_for(settings(), code, fy)
        try:
            rows, problem = figure_rows(ws), None
        except FiguresFileProblem as exc:
            rows, problem = [], str(exc)
        selected = next((f for f in rows if f.figure_id == request.args.get("view")), None)
        source = find_document(ws, selected.doc_id) if selected and selected.doc_id else None
        return render_template("client_figures.html", **client_context(ws, "figures"), rows=rows, problem=problem,
                               selected=selected, source=source, labels=label_choices(), docs=documents(ws),
                               doc_types=load_doc_types())

    @app.post("/c/<code>/<int:fy>/figures/<figure_id>")
    def figure_set(code: str, fy: int, figure_id: str):
        ws = workspace_for(settings(), code, fy)
        form = request.form
        try:
            current = next((f for f in figure_rows(ws) if f.figure_id == figure_id), None)
            if current is None:
                raise ValueError(f"There's no figure {figure_id}.")
            substantiated = True if "substantiated" in form else (None if current.substantiated is None else False)
            set_figure(ws, figure_id, confirmed="confirmed" in form, substantiated=substantiated,
                       label_key=form.get("label_key") or None, amount=form.get("amount") or None,
                       audit=audit_for(code))
        except (ValueError, SensitiveDataBlocked, FileLockedError, OSError) as exc:
            flash(_figures_problem(exc), "error")
        return redirect(f"{base_url(ws)}/figures?view={figure_id}#{figure_id}")

    @app.post("/c/<code>/<int:fy>/figures/new")
    def figure_new(code: str, fy: int):
        ws = workspace_for(settings(), code, fy)
        form = request.form
        try:
            page = int(form["page"]) if (form.get("page") or "").strip() else None
            added = add_figure(ws, label_key=form.get("label_key") or "", description=form.get("description") or "",
                               amount=form.get("amount") or "", doc_id=form.get("doc_id") or None, page=page,
                               audit=audit_for(code))
        except (ValueError, SensitiveDataBlocked, FileLockedError, OSError) as exc:
            flash(_figures_problem(exc), "error")
            return redirect(f"{base_url(ws)}/figures#add")
        flash(f"{added.figure_id} added. Tick Confirmed once you've checked it against its source.", "ok")
        return redirect(f"{base_url(ws)}/figures?view={added.figure_id}#{added.figure_id}")

    @app.get("/c/<code>/<int:fy>/prepare")
    def prepare_tab(code: str, fy: int):
        ws = workspace_for(settings(), code, fy)
        return render_template("client_prepare.html", **client_context(ws, "prepare"), summary=load_summary(ws),
                               components=COMPONENTS, papers=workpapers(ws))

    @app.post("/c/<code>/<int:fy>/prepare")
    def prepare_run(code: str, fy: int):
        ws = workspace_for(settings(), code, fy)
        try:
            summary = run_prepare(ws, audit_for(code), getpass.getuser())
        except (PrepareError, RatesError, ValueError, SensitiveDataBlocked, FileLockedError, OSError) as exc:
            flash(problem_text(exc), "error")
        else:
            flash(f"{summary.workpaper} prepared.", "ok")
        return redirect(f"{base_url(ws)}/prepare")

    @app.get("/c/<code>/<int:fy>/workpaper/<name>")
    def workpaper_download(code: str, fy: int, name: str):
        ws = workspace_for(settings(), code, fy)
        path = next((p for p in workpapers(ws) if p.name == name), None)
        if path is None:
            abort(404)
        return send_file(path, as_attachment=True, download_name=path.name, max_age=0,
                         mimetype="application/vnd.openxmlformats-officedocument.spreadsheetml.sheet")

    @app.get("/c/<code>/<int:fy>/review")
    def review_tab(code: str, fy: int):
        ws = workspace_for(settings(), code, fy)
        summary, review, citations = load_summary(ws), load_review(ws), load_citations()
        items = []
        for n in summary.notes if summary else []:
            key = note_key(n)
            items.append({"note": n, "key": key, "citation": citation_text(citations, n.citation_id),
                          "response": review.responses.get(key, {})})
        current = {i["key"] for i in items}
        old = [(k, v) for k, v in review.responses.items() if k not in current]
        counts = {r: sum(i["note"].risk == r for i in items) for r in ("High", "Medium", "Low")}
        return render_template("client_review.html", **client_context(ws, "review"), summary=summary, items=items,
                               old=old, counts=counts, reviewed=review.reviewed)

    @app.post("/c/<code>/<int:fy>/review/response")
    def review_response(code: str, fy: int):
        ws = workspace_for(settings(), code, fy)
        summary = load_summary(ws)
        key = request.form.get("key") or ""
        try:
            if not summary or key not in {note_key(n) for n in summary.notes}:
                raise ValueError("That note is no longer raised by the latest workpaper. Reload the page.")
            audit_for(code)
            save_response(ws, key, request.form.get("text") or "", "resolved" in request.form, getpass.getuser())
        except (ValueError, SensitiveDataBlocked, FileLockedError, OSError) as exc:
            flash(problem_text(exc), "error")
        return redirect(f"{base_url(ws)}/review#n-{key.split('|')[0]}")

    @app.post("/c/<code>/<int:fy>/review/mark")
    def review_mark(code: str, fy: int):
        ws = workspace_for(settings(), code, fy)
        summary = load_summary(ws)
        try:
            if not summary or job_status(ws) not in ("Prepared", "Reviewed"):
                raise ValueError("Prepare the return again first: the figures have changed since the last workpaper.")
            mark_reviewed(ws, request.form.get("name") or "", summary.workpaper, summary.notes, audit_for(code))
        except (ValueError, SensitiveDataBlocked, FileLockedError, OSError) as exc:
            flash(problem_text(exc), "error")
        else:
            flash("Marked reviewed. The registered agent still signs the workpaper's Cover tab.", "ok")
        return redirect(f"{base_url(ws)}/review")
