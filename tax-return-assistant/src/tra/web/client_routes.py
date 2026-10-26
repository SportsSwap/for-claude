"""A client's pages: Files, Figures, Prepare, Review notes, Notes."""

from __future__ import annotations

import getpass
import mimetypes
import os
import secrets
from datetime import date
from pathlib import Path

from flask import Flask, abort, current_app, flash, redirect, render_template, request, send_file

from ..ingest.classify import load_doc_types
from ..filing.fyi_store import make_store
from ..ingest.extractors.ai_reader import TEXT_MATCH, AiReaderUnavailable, ai_reader_from_settings
from ..privacy.guard import FileLockedError, SensitiveDataBlocked
from ..checks import load_citations
from ..review_store import load_review, mark_reviewed, note_key, save_response
from ..run import PrepareError
from ..taxcalc.rates import RatesError
from ..workpaper.build import citation_text
from ..workspace import Workspace
from ..cabinets import CABINET_BY_CODE, CabinetSpace
from ..doc_notes import STATUSES, load_doc_notes, save_doc_note
from ..doc_props import set_properties
from ..trash import deleted_documents
from ..versions import add_version, list_versions, version_path
from ..doc_summary import summaries
from ..to_check import things_to_check, to_check_by_figure
from .client_names import load_names, set_name
from .comments import list_comments
from .client_notes import add_note, delete_note, edit_note, list_notes
from .messages import problem_text
from .routes import audit_for, settings
from .services.clients import workspace_for
from .services.files import add_folder, document_path, documents, find_document, folder_names, folders, move_document
from .services.figures import (FiguresFileProblem, add_figure, confirm_document_figures, figure_rows, label_choices,
                               set_figure, waiting_by_document)
from .services.imports import RETURN_TYPES, import_file, store_upload_in_cabinet
from .services.activity import activity
from .services.prepare import COMPONENTS, load_summary, run_prepare, workpapers
from .status import job_status

INLINE_TYPES = {"application/pdf", "image/png", "image/jpeg"}


def client_context(ws: Workspace, tab: str) -> dict:
    name = load_names(ws.tra_home).get(ws.client_code)
    return {"client": {"code": ws.client_code, "name": name, "fy": ws.income_year, "status": job_status(ws),
                       "tab": tab}, "nav": "clients"}


def base_url(ws: Workspace) -> str:
    return f"/c/{ws.client_code}/{ws.income_year}"


def space_of(ws: Workspace):
    """The year's Tax return workspace, or the client's Permanent/Correspondence cabinet (?cab=PERM / CORR)."""
    cab = (request.values.get("cab") or "").strip()
    if not cab:
        return ws
    if cab not in CABINET_BY_CODE:
        abort(404)
    return CabinetSpace(ws.tra_home, ws.client_code, CABINET_BY_CODE[cab])


def cab_q(space) -> str:
    return f"cab={space.code}&" if isinstance(space, CabinetSpace) else ""


def unconfirmed_ids(ws: Workspace, doc_id: str) -> list[str]:
    """Figures from this Tax return document still waiting to be confirmed (pre-fill rows aside)."""
    try:
        return waiting_by_document(figure_rows(ws)).get(doc_id, [])
    except FiguresFileProblem:
        return []  # the Figures tab explains the rows to fix


def render_files(ws: Workspace, folder: str | None, view_id: str = "", results=None, status: int = 200, space=None):
    space = space or ws
    names = folder_names(space)
    folder = folder if folder in names else None
    from .home_routes import doclist_context
    from .services.doclist import all_documents

    if isinstance(space, CabinetSpace):
        rows = all_documents(ws.tra_home, code=ws.client_code, cabinet=space.cabinet)
    else:
        rows = all_documents(ws.tra_home, code=ws.client_code, income_year=ws.income_year, cabinet="Tax return")
    listing = doclist_context(rows, f"{base_url(ws)}/files", fixed={"client": "", "year": "", "folder": folder or ""})
    return render_template("client_files.html", **client_context(ws, "files"), folders=folders(space), folder=folder,
                           view=find_document(space, view_id), folder_names=names, doc_types=load_doc_types(),
                           results=results, return_types=RETURN_TYPES, summaries=summaries(space),
                           descriptions=load_doc_notes(space), total=len(rows), folders_for_move=names,
                           space=space, cabinet=getattr(space, "cabinet", "Tax return"), cabq=cab_q(space),
                           cab=getattr(space, "code", ""), statuses=STATUSES,
                           deleted_count=len(deleted_documents(space)),
                           versions=list_versions(space, view_id) if view_id else [],
                           view_checks=things_to_check(space, view_id) if view_id and space is ws else [],
                           view_unconfirmed=unconfirmed_ids(ws, view_id) if view_id and space is ws else [],
                           doc_key=f"{ws.client_code}/{getattr(space, 'code', None) or ws.income_year}/{view_id}",
                           doc_comments=list_comments(ws.tra_home, ws.client_code,
                                                      f"doc:{ws.client_code}/{getattr(space, 'code', None) or ws.income_year}/{view_id}")
                           if view_id else [], **listing), status


def register_client_routes(app: Flask) -> None:
    @app.get("/c/<code>/<int:fy>/files")
    def files(code: str, fy: int):
        ws = workspace_for(settings(), code, fy)
        return render_files(ws, request.args.get("folder"), request.args.get("view", ""), space=space_of(ws))

    @app.post("/c/<code>/<int:fy>/folders")
    def folder_add(code: str, fy: int):
        ws = workspace_for(settings(), code, fy)
        space = space_of(ws)
        name = (request.form.get("name") or "").strip()
        try:
            add_folder(space, name, audit_for(code))
        except (ValueError, SensitiveDataBlocked, OSError) as exc:
            flash(problem_text(exc), "error")
            return redirect(f"{base_url(ws)}/files?{cab_q(space)}")
        flash(f"Folder {name} added.", "ok")
        return redirect(f"{base_url(ws)}/files?{cab_q(space)}folder={name}")

    @app.get("/c/<code>/<int:fy>/doc/<doc_id>")
    def doc_view(code: str, fy: int, doc_id: str):
        ws = workspace_for(settings(), code, fy)
        space = space_of(ws)
        doc = find_document(space, doc_id)
        if doc is None:
            abort(404)
        path = document_path(space, doc_id)
        if path is None:
            return render_template("error.html", title="Filed in FYI", text=f"{doc.filed_name} is filed in FYI. "
                                   "Open it there.", reference=None, nav="clients")
        mimetype = mimetypes.guess_type(path.name)[0] or "application/octet-stream"
        return send_file(path, mimetype=mimetype, as_attachment=mimetype not in INLINE_TYPES,
                         download_name=doc.filed_name, max_age=0)

    @app.post("/c/<code>/<int:fy>/doc/<doc_id>/move")
    def doc_move(code: str, fy: int, doc_id: str):
        ws = workspace_for(settings(), code, fy)
        space = space_of(ws)
        folder = request.form.get("folder") or ""
        try:
            moved = move_document(space, doc_id, folder, audit_for(code))
        except (ValueError, SensitiveDataBlocked, FileLockedError, OSError) as exc:
            flash(problem_text(exc), "error")
            return redirect(f"{base_url(ws)}/files?{cab_q(space)}view={doc_id}")
        flash(f"{moved.filed_name} moved to {folder}.", "ok")
        return redirect(f"{base_url(ws)}/files?{cab_q(space)}folder={folder}&view={doc_id}")

    @app.post("/c/<code>/<int:fy>/import")
    def import_docs(code: str, fy: int):
        ws = workspace_for(settings(), code, fy)
        space = space_of(ws)
        uploads = [u for u in request.files.getlist("files") if u and u.filename]
        if not uploads:
            flash("Choose at least one file to import.", "error")
            return redirect(f"{base_url(ws)}/files?{cab_q(space)}")
        # The progress bar sends one file at a time and asks for just its results (fragment=1).
        fragment = request.form.get("fragment") == "1"
        try:
            first = max(1, int(request.form.get("first_position") or 1))
        except ValueError:
            first = 1

        def done(results):
            if fragment:
                return render_template("_import_results.html", results=results, doc_types=load_doc_types())
            return render_files(ws, None, results=results, space=space)

        if isinstance(space, CabinetSpace):
            audit = audit_for(code)
            results = [store_upload_in_cabinet(space, upload, folder=request.form.get(f"folder_{i}") or "Other",
                                               audit=audit, position=first + i)
                       for i, upload in enumerate(uploads)]
            return done(results)
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
                               position=first + i, ai_reader=ai_reader)
                   for i, upload in enumerate(uploads)]
        return done(results)

    @app.post("/c/<code>/<int:fy>/doc/<doc_id>/reread")
    def doc_reread(code: str, fy: int, doc_id: str):
        from ..reread import reread_document

        ws = workspace_for(settings(), code, fy)
        try:
            r = reread_document(ws, doc_id, audit_for(code))
        except (ValueError, SensitiveDataBlocked, FileLockedError, OSError) as exc:
            flash(problem_text(exc), "error")
        else:
            how = f" with the learned layout {r.layout}" if r.layout else ""
            flash(f"{doc_id} read again{how}: {r.added} figure{'' if r.added == 1 else 's'} added, {r.removed} "
                  "replaced. Figures you'd confirmed or typed in weren't changed." + (f" {r.note}" if r.note else ""),
                  "ok")
        return redirect(f"{base_url(ws)}/files?view={doc_id}")

    @app.post("/c/<code>/<int:fy>/info-request")
    def info_request(code: str, fy: int):
        from ..info_request import make_info_request

        ws = workspace_for(settings(), code, fy)
        try:
            doc = make_info_request(ws, audit_for(code))
        except (ValueError, SensitiveDataBlocked, FileLockedError, OSError) as exc:
            flash(problem_text(exc), "error")
            return redirect(f"{base_url(ws)}/files")
        flash(f"Info request filed in Correspondence, Letters, as {doc.filed_name}. Use Open to edit it in Word, "
              "type the client's name, then send it.", "ok")
        return redirect(f"{base_url(ws)}/files?cab=CORR&view={doc.doc_id}")

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
        docs, doc_types = documents(ws), load_doc_types()
        kinds = {d.doc_id: doc_types[d.doc_type].description if d.doc_type in doc_types else d.doc_type for d in docs}
        by_document = [{"doc_id": doc_id, "kind": kinds.get(doc_id, ""), "count": len(ids), "ids": ids}
                       for doc_id, ids in waiting_by_document(rows).items() if doc_id in kinds]
        return render_template("client_figures.html", **client_context(ws, "figures"), rows=rows, problem=problem,
                               selected=selected, source=source, labels=label_choices(), docs=docs,
                               doc_types=doc_types, checks=to_check_by_figure(ws) if not problem else {},
                               by_document=by_document, text_match=TEXT_MATCH)

    @app.post("/c/<code>/<int:fy>/doc/<doc_id>/confirm-all")
    def doc_confirm_all(code: str, fy: int, doc_id: str):
        from .home_routes import _safe_next

        ws = workspace_for(settings(), code, fy)
        target = _safe_next(request.form.get("next"), f"{base_url(ws)}/files?view={doc_id}")
        # Only the figures the page showed: one that arrived since (Excel, Read again, tra ai-add) hasn't been checked.
        shown = [i.strip() for v in request.form.getlist("figure_id") for i in v.split(",") if i.strip()]
        try:
            n, newer = confirm_document_figures(ws, doc_id, audit_for(code), figure_ids=shown)
        except (ValueError, SensitiveDataBlocked, FileLockedError, OSError) as exc:
            flash(_figures_problem(exc), "error")
            return redirect(target)
        s = "" if n == 1 else "s"
        if n and newer:
            flash(f"{n} figure{s} confirmed. {newer} more from {doc_id} arrived since you opened the page; check "
                  "them before confirming.", "ok")
        elif n:
            flash(f"{n} figure{s} from {doc_id} confirmed. They'll be in the return the next time you prepare it.",
                  "ok")
        else:
            flash(f"Nothing to confirm in {doc_id}.", "ok")
        return redirect(target)

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

    @app.post("/c/<code>/name")
    def client_rename(code: str):
        try:
            fy = int(request.form.get("fy") or 0)
        except ValueError:
            fy = 0
        ws = workspace_for(settings(), code, fy)
        try:
            set_name(settings().tra_home, code, request.form.get("name") or "", audit_for(code))
        except (ValueError, SensitiveDataBlocked, FileLockedError, OSError) as exc:
            flash(problem_text(exc), "error")
        else:
            flash("Name saved.", "ok")
        return redirect(f"{base_url(ws)}/files")

    @app.post("/c/<code>/<int:fy>/doc/<doc_id>/description")
    def doc_description(code: str, fy: int, doc_id: str):
        ws = workspace_for(settings(), code, fy)
        space = space_of(ws)
        if find_document(space, doc_id) is None:
            abort(404)
        try:
            audit_for(code)
            save_doc_note(space, doc_id, request.form.get("text") or "", getpass.getuser())
        except (ValueError, SensitiveDataBlocked, FileLockedError, OSError) as exc:
            flash(problem_text(exc), "error")
        else:
            flash("Description saved.", "ok")
        return redirect(f"{base_url(ws)}/files?{cab_q(space)}view={doc_id}")

    @app.post("/c/<code>/<int:fy>/doc/<doc_id>/properties")
    def doc_properties(code: str, fy: int, doc_id: str):
        ws = workspace_for(settings(), code, fy)
        space = space_of(ws)
        if find_document(space, doc_id) is None:
            abort(404)
        form = request.form
        try:
            raw_date = (form.get("doc_date") or "").strip()
            when = date.fromisoformat(raw_date) if raw_date else None
            doc, warnings = set_properties(space, doc_id, doc_type=form.get("doc_type") or "",
                                           folder=form.get("folder") or "", doc_date=when,
                                           status=form.get("status") or "", by=getpass.getuser(),
                                           audit=audit_for(code))
        except (ValueError, SensitiveDataBlocked, FileLockedError, OSError) as exc:
            flash(problem_text(exc), "error")
            return redirect(f"{base_url(ws)}/files?{cab_q(space)}view={doc_id}")
        for warning in warnings:
            flash(warning, "error")
        flash("Properties saved.", "ok")
        return redirect(f"{base_url(ws)}/files?{cab_q(space)}folder={doc.category}&view={doc_id}")

    @app.post("/c/<code>/<int:fy>/doc/<doc_id>/version")
    def doc_version(code: str, fy: int, doc_id: str):
        ws = workspace_for(settings(), code, fy)
        space = space_of(ws)
        if find_document(space, doc_id) is None:
            abort(404)
        upload = request.files.get("file")
        if not upload or not upload.filename:
            flash("Choose the newer copy first.", "error")
            return redirect(f"{base_url(ws)}/files?{cab_q(space)}view={doc_id}")
        temp = space.work_dir / "_uploads" / f"{secrets.token_hex(8)}{Path(upload.filename).suffix.lower()}"
        temp.parent.mkdir(parents=True, exist_ok=True)
        try:
            upload.save(temp)
            warnings = add_version(space, doc_id, temp, getpass.getuser(), audit_for(code))
        except (ValueError, SensitiveDataBlocked, FileLockedError, OSError) as exc:
            flash(problem_text(exc), "error")
        else:
            for warning in warnings:
                flash(warning, "error")
            flash("New version saved; the older copy is listed below it.", "ok")
        finally:
            temp.unlink(missing_ok=True)
        return redirect(f"{base_url(ws)}/files?{cab_q(space)}view={doc_id}")

    @app.get("/c/<code>/<int:fy>/doc/<doc_id>/v/<int:n>")
    def doc_old_version(code: str, fy: int, doc_id: str, n: int):
        ws = workspace_for(settings(), code, fy)
        space = space_of(ws)
        doc = find_document(space, doc_id)
        path = version_path(space, doc_id, n) if doc else None
        if path is None:
            abort(404)
        mimetype = mimetypes.guess_type(path.name)[0] or "application/octet-stream"
        return send_file(path, mimetype=mimetype, as_attachment=mimetype not in INLINE_TYPES,
                         download_name=f"{Path(doc.filed_name).stem}_v{n}{path.suffix}", max_age=0)
