"""Sawnx pages. Each view reads the request, calls a service, and renders a template."""

from __future__ import annotations

import os

from flask import Flask, current_app, flash, redirect, render_template, request

from ..clients import ClientExists, create_client
from ..paths import CONFIG_DIR
from ..privacy import guard
from ..privacy.guard import SensitiveDataBlocked, check_text
from ..privacy.audit import AuditLog
from .. import settings as tra_settings
from ..settings import Settings, validate_client_code
from .client_names import set_name, suggest_code
from .messages import GUARD_MESSAGE
from .services.clients import list_clients
from .status import STATUSES

AGE_BANDS = {"under65": "Under 65", "65to69": "65 to 69", "70plus": "70 or over"}
SAPTO = {"none": "Not eligible", "single": "Single", "couple": "Couple", "illness_separated": "Illness-separated"}


def settings() -> Settings:
    return current_app.config["SAWNX"]["settings"]


def audit_for(code: str | None) -> AuditLog:
    """The audit log, with guard blocks recorded against this client (as the CLI does)."""
    tra_home = settings().tra_home
    from ..workspace import Workspace

    audit = AuditLog(Workspace(tra_home, code or "-", 0).audit_path)
    guard.set_block_listener(lambda location, kind: audit.record("guard_blocked", client=code, location=location,
                                                                 detector=kind))
    return audit


def income_years() -> list[int]:
    return sorted((int(p.stem[2:]) for p in (CONFIG_DIR / "rates").glob("fy*.yaml") if p.stem[2:].isdigit()),
                  reverse=True)


def _client_options(form) -> tuple[dict, list[str]]:
    errors = []
    try:
        dependants = int(form.get("dependants") or 0)
        if not 0 <= dependants <= 20:
            raise ValueError
    except ValueError:
        errors.append("Dependants must be a number from 0 to 20.")
        dependants = 0
    raw_days = (form.get("hospital_days") or "").strip()
    days = None
    if raw_days:
        try:
            days = int(raw_days)
            if not 0 <= days <= 366:
                raise ValueError
        except ValueError:
            errors.append("Hospital cover days must be a number from 0 to 366, or left blank if unknown.")
    age_band = form.get("age_band") or "under65"
    sapto = form.get("sapto") or "none"
    if age_band not in AGE_BANDS or sapto not in SAPTO:
        errors.append("Choose an age band and seniors offset status from the lists.")
    return dict(help_debt="help_debt" in form, sole_trader="sole_trader" in form, age_band=age_band,
                sapto_status=sapto, has_spouse="spouse" in form, dependants=dependants, hospital_cover_days=days,
                resident="non_resident" not in form), errors


def _ai_model_name() -> str:
    from ..ingest.extractors.ai_reader import DEFAULT_MODEL, MODEL_NAMES

    return MODEL_NAMES.get(DEFAULT_MODEL, DEFAULT_MODEL)


def register(app: Flask) -> None:
    @app.get("/clients")
    def clients():
        rows = list_clients(settings().tra_home)
        counts = {s: sum(r.status == s for r in rows) for s in STATUSES}
        q = (request.args.get("q") or "").strip()
        status = request.args.get("status") or ""
        shown = [r for r in rows if (not q or q.lower() in (r.name or "").lower() or r.code.startswith(q.upper()))
                 and (not status or r.status == status)]
        return render_template("clients.html", rows=shown, total=len(rows), counts=counts, q=q, status=status,
                               statuses=STATUSES)

    @app.route("/clients/new", methods=["GET", "POST"])
    def client_new():
        years = income_years()
        form = request.form if request.method == "POST" else {}
        errors: list[str] = []
        if request.method == "POST":
            name = " ".join((form.get("name") or "").split())
            code = (form.get("code") or "").strip()
            work = settings().tra_home / "Work"
            if name and not code:
                code = suggest_code(name, {p.name for p in work.iterdir()} if work.is_dir() else set())
            if not name and not code:
                errors.append("Enter the client's name (and the firm's client code if it has one).")
            try:
                year = int(form.get("income_year") or 0)
            except ValueError:
                year = 0
            if year not in years:
                errors.append("Choose an income year from the list.")
            try:
                validate_client_code(code, settings().client_code_pattern)
            except ValueError:
                if code:
                    errors.append(f"{code!r} isn't a valid client code. Use the firm's client code in capitals, "
                                  "like SMIT01. The name goes in the name box.")
            if name:
                try:
                    check_text(name, "client name")
                except SensitiveDataBlocked:
                    errors.append(GUARD_MESSAGE)
            options, option_errors = _client_options(form)
            errors += option_errors
            if not errors:
                try:
                    audit = audit_for(code)
                    create_client(settings().tra_home, code, year, options, audit)
                    if name:
                        set_name(settings().tra_home, code, name, audit)
                except ClientExists as exc:
                    errors.append(str(exc))
                else:
                    return redirect(f"/c/{code}/{year}/files")
        return render_template("client_new.html", form=form, errors=errors, years=years, age_bands=AGE_BANDS,
                               sapto=SAPTO), 200

    @app.get("/layouts")
    def layouts_page():
        from ..ingest.classify import load_doc_types
        from ..ingest.layouts import load_layouts
        from ..reread import all_waiting, layout_counts
        from .client_names import load_names

        tra_home = settings().tra_home
        learned, problems = load_layouts()
        counts = layout_counts(tra_home)
        names = load_names(tra_home)
        waiting = [{"code": ws.client_code, "fy": ws.income_year, "name": names.get(ws.client_code), "doc": d}
                   for ws, d in all_waiting(tra_home)]
        return render_template("layouts.html", nav="settings", learned=learned, problems=problems, counts=counts,
                               waiting=waiting, doc_types=load_doc_types())

    @app.get("/settings")
    def settings_page():
        from .app_settings import load_app_settings
        from .context import unverified_years
        from .work_routes import rules_context

        s = settings()
        env = os.environ
        fyi_ready = all((env.get(n) or tra_settings.saved_user_variable(n)).strip() for n in
                        ("FYI_BASE_URL", "FYI_ACCESS_ID", "FYI_ACCESS_SECRET", "FYI_APP_ID"))
        years = income_years()
        return render_template("settings.html", nav="settings", app_settings=load_app_settings(s.tra_home),
                               store=s.store, fyi_ready=fyi_ready, xero_ready=bool(env.get("XERO_CLIENT_ID")
                                                                                  or tra_settings.saved_user_variable("XERO_CLIENT_ID")),
                               key_set=bool((env.get("ANTHROPIC_API_KEY") or "").strip()
                                            or tra_settings.saved_user_variable("ANTHROPIC_API_KEY").strip()),
                               ai_model=_ai_model_name(), years=years,
                               unverified=unverified_years(years), port=current_app.config["SAWNX"]["port"],
                               **rules_context(s.tra_home))

    @app.post("/settings/ai-reader")
    def settings_ai_reader():
        from datetime import date

        from .app_settings import disable_ai_reader, enable_ai_reader, load_app_settings
        from .messages import problem_text

        audit = audit_for(None)
        try:
            if request.form.get("action") == "on":
                raw = (request.form.get("approved_on") or "").strip()
                enable_ai_reader(settings().tra_home, request.form.get("approved_by") or "",
                                 date.fromisoformat(raw) if raw else None, audit)
                if load_app_settings(settings().tra_home).page_images_in_use:  # switched on again while on
                    flash("AI reader switched on. It receives blanked-out text, and pictures of scanned pages, "
                          "which aren't blanked out (page images are on).", "ok")
                else:
                    flash("AI reader switched on. It only receives blanked-out text.", "ok")
            else:
                images_were_on = load_app_settings(settings().tra_home).ai_page_images
                disable_ai_reader(settings().tra_home, audit)
                flash("AI reader switched off." + (" Page images are off too." if images_were_on else ""), "ok")
        except (ValueError, OSError) as exc:
            flash(problem_text(exc), "error")
        return redirect("/settings")

    @app.post("/settings/ai-page-images")
    def settings_ai_page_images():
        from datetime import date

        from .app_settings import disable_ai_page_images, enable_ai_page_images
        from .messages import problem_text

        audit = audit_for(None)
        try:
            if request.form.get("action") == "on":
                raw = (request.form.get("approved_on") or "").strip()
                enable_ai_page_images(settings().tra_home, request.form.get("approved_by") or "",
                                      date.fromisoformat(raw) if raw else None, audit)
                flash("Page images switched on. Scanned pages go to Anthropic as pictures, which aren't blanked "
                      "out.", "ok")
            else:
                disable_ai_page_images(settings().tra_home, audit)
                flash("Page images switched off. Only blanked-out text is sent.", "ok")
        except (ValueError, OSError) as exc:
            flash(problem_text(exc), "error")
        return redirect("/settings")

    from .client_routes import register_client_routes
    from .home_routes import register_home_routes, register_intray_routes
    from .trash_routes import register_trash_routes
    from .work_routes import register_work_routes

    register_client_routes(app)
    register_home_routes(app)
    register_intray_routes(app)
    register_work_routes(app)
    register_trash_routes(app)
