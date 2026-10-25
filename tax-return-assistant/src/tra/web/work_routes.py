"""Jobs, tasks, comments, time, Knowledge and filing rules (FYI-style stages 3-5)."""

from __future__ import annotations

import getpass
import mimetypes
import secrets
from pathlib import Path

from flask import Flask, abort, flash, redirect, render_template, request, send_file

from ..cabinets import CABINETS
from ..privacy.guard import FileLockedError, SensitiveDataBlocked
from .client_names import load_names
from .comments import add_comment, list_comments
from .home_routes import _safe_next  # the same rule as every other page
from .jobs import (JOB_STATUSES, add_job, add_task, client_years, find_job, list_jobs, list_tasks, set_task_done,
                   update_job)
from .knowledge import KNOWLEDGE_FOLDERS, knowledge_dir, knowledge_docs, knowledge_path, store_knowledge
from .messages import problem_text
from .routes import audit_for, settings
from .rules import add_rule, delete_rule, folders_for
from .timesheet import add_time, list_time

PROBLEMS = (ValueError, SensitiveDataBlocked, FileLockedError, OSError)




def register_work_routes(app: Flask) -> None:
    @app.get("/jobs")
    def jobs_page():
        tra_home = settings().tra_home
        names = load_names(tra_home)
        jobs = list_jobs(tra_home)
        f = {k: (request.args.get(k) or "").strip() for k in ("client", "status", "assignee", "q")}
        shown = [j for j in jobs
                 if (not f["client"] or j.code == f["client"]) and (not f["status"] or j.status == f["status"])
                 and (not f["assignee"] or j.assignee.lower() == f["assignee"].lower())
                 and (not f["q"] or f["q"].lower() in f"{j.name} {names.get(j.code, j.code)} {j.notes}".lower())]
        shown.sort(key=lambda j: (j.done, j.due is None, j.due or 0, names.get(j.code, j.code).lower()))
        statuses = sorted({j.status for j in jobs})
        return render_template("jobs.html", nav="jobs", jobs=shown, total=len(jobs), names=names, f=f,
                               statuses=statuses, assignees=sorted({j.assignee for j in jobs if j.assignee}),
                               clients=sorted(client_years(tra_home), key=lambda c: names.get(c, c).lower()))

    @app.post("/jobs")
    def job_new():
        form = request.form
        try:
            job = add_job(settings().tra_home, form.get("code") or "", form.get("name") or "", due=form.get("due") or "",
                          assignee=form.get("assignee") or "", notes=form.get("notes") or "", by=getpass.getuser(),
                          audit=audit_for(form.get("code") or None))
        except PROBLEMS as exc:
            flash(problem_text(exc), "error")
            return redirect("/jobs")
        flash(f"Job \"{job.name}\" added.", "ok")
        return redirect(f"/jobs/{job.id}")

    @app.get("/jobs/<job_id>")
    def job_page(job_id: str):
        tra_home = settings().tra_home
        job = find_job(tra_home, job_id)
        if job is None:
            abort(404)
        tasks = [t for t in list_tasks(tra_home) if t.job_id == job_id]
        time = list_time(tra_home, job_id)
        return render_template("job.html", nav="jobs", job=job, client=load_names(tra_home).get(job.code, job.code),
                               tasks=tasks, comments=list_comments(tra_home, job.code, f"job:{job_id}"),
                               time=time, total_minutes=sum(e["minutes"] for e in time), statuses=JOB_STATUSES,
                               link_year=(client_years(tra_home).get(job.code) or [None])[0])

    @app.post("/jobs/<job_id>")
    def job_update(job_id: str):
        form = request.form
        job = find_job(settings().tra_home, job_id)
        if job is None:
            abort(404)
        try:
            update_job(settings().tra_home, job_id, status=form.get("status") if job.kind == "custom" else None,
                       due=form.get("due", ""), assignee=form.get("assignee", ""), notes=form.get("notes", ""),
                       audit=audit_for(job.code))
        except PROBLEMS as exc:
            flash(problem_text(exc), "error")
        else:
            flash("Job saved.", "ok")
        return redirect(f"/jobs/{job_id}")

    @app.post("/jobs/<job_id>/tasks")
    def job_task(job_id: str):
        form = request.form
        try:
            add_task(settings().tra_home, form.get("title") or "", job_id=job_id, due=form.get("due") or "",
                     assignee=form.get("assignee") or "", by=getpass.getuser(), audit=audit_for(None))
        except PROBLEMS as exc:
            flash(problem_text(exc), "error")
        return redirect(f"/jobs/{job_id}")

    @app.post("/jobs/<job_id>/time")
    def job_time(job_id: str):
        form = request.form
        try:
            add_time(settings().tra_home, job_id, form.get("date") or "", form.get("minutes") or "",
                     form.get("what") or "", getpass.getuser(), audit_for(None))
        except PROBLEMS as exc:
            flash(problem_text(exc), "error")
        else:
            flash("Time recorded.", "ok")
        return redirect(f"/jobs/{job_id}")

    @app.post("/tasks")
    def task_new():
        form = request.form
        try:
            add_task(settings().tra_home, form.get("title") or "", job_id=None, due=form.get("due") or "",
                     assignee=form.get("assignee") or "", by=getpass.getuser(), audit=audit_for(None))
        except PROBLEMS as exc:
            flash(problem_text(exc), "error")
        return redirect(_safe_next(form.get("next"), "/?tab=tasks"))

    @app.post("/tasks/<task_id>/done")
    def task_done(task_id: str):
        try:
            set_task_done(settings().tra_home, task_id, "done" in request.form, audit_for(None))
        except PROBLEMS as exc:
            flash(problem_text(exc), "error")
        return redirect(_safe_next(request.form.get("next"), "/?tab=tasks"))

    @app.post("/comments")
    def comment_new():
        form = request.form
        code = form.get("code") or ""
        if code not in client_years(settings().tra_home):
            abort(404)
        try:
            add_comment(settings().tra_home, code, form.get("target") or "", form.get("text") or "",
                        getpass.getuser(), audit_for(code))
        except PROBLEMS as exc:
            flash(problem_text(exc), "error")
        return redirect(_safe_next(form.get("next")))

    @app.get("/knowledge")
    def knowledge_page():
        folder = request.args.get("folder") if request.args.get("folder") in KNOWLEDGE_FOLDERS else None
        docs = knowledge_docs(settings().tra_home)
        counts = {f: sum(d.category == f for d in docs) for f in KNOWLEDGE_FOLDERS}
        return render_template("knowledge.html", nav="knowledge", folders=KNOWLEDGE_FOLDERS, folder=folder,
                               counts=counts, docs=[d for d in docs if folder is None or d.category == folder])

    @app.post("/knowledge")
    def knowledge_add():
        uploads = [u for u in request.files.getlist("files") if u and u.filename]
        folder = request.form.get("folder") or "Other"
        if not uploads:
            flash("Choose at least one file.", "error")
            return redirect("/knowledge")
        tra_home = settings().tra_home
        for upload in uploads:
            temp = knowledge_dir(tra_home) / "_incoming" / f"{secrets.token_hex(8)}{Path(upload.filename).suffix.lower()}"
            temp.parent.mkdir(parents=True, exist_ok=True)
            try:
                upload.save(temp)
                doc = store_knowledge(tra_home, temp, Path(upload.filename).name, folder, getpass.getuser(),
                                      audit_for(None))
                flash(f"{doc.filed_name} added to {folder}.", "ok")
            except PROBLEMS as exc:
                flash(problem_text(exc), "error")
            finally:
                temp.unlink(missing_ok=True)
        return redirect(f"/knowledge?folder={folder}")

    @app.get("/knowledge/<doc_id>")
    def knowledge_open(doc_id: str):
        path = knowledge_path(settings().tra_home, doc_id)
        if path is None:
            abort(404)
        mimetype = mimetypes.guess_type(path.name)[0] or "application/octet-stream"
        inline = mimetype in {"application/pdf", "image/png", "image/jpeg"}
        return send_file(path, mimetype=mimetype, as_attachment=not inline, download_name=path.name, max_age=0)

    @app.post("/settings/rules")
    def rule_new():
        form = request.form
        try:
            add_rule(settings().tra_home, form.get("phrase") or "", form.get("code") or "", form.get("cabinet") or "",
                     form.get("folder") or "", audit_for(form.get("code") or None))
        except PROBLEMS as exc:
            flash(problem_text(exc), "error")
        else:
            flash("Filing rule added. It changes In Tray suggestions only.", "ok")
        return redirect("/settings#rules")

    @app.post("/settings/rules/<rule_id>/delete")
    def rule_delete(rule_id: str):
        try:
            delete_rule(settings().tra_home, rule_id, audit_for(None))
        except PROBLEMS as exc:
            flash(problem_text(exc), "error")
        return redirect("/settings#rules")


def rules_context(tra_home: Path) -> dict:
    from .rules import load_rules

    names = load_names(tra_home)
    return {"rules": load_rules(tra_home), "rule_clients": sorted(client_years(tra_home), key=lambda c: names.get(c, c).lower()),
            "rule_names": names, "rule_cabinets": CABINETS,
            "rule_folders": {c: folders_for(c) for c in CABINETS}}
