"""Values every page needs: the rates warning and whether the AI reader is on."""

from __future__ import annotations

from flask import Flask, current_app

from ..taxcalc.rates import RatesError, load_rates


def unverified_years(years: list[int]) -> list[int]:
    out = []
    for year in years:
        try:
            if load_rates(year).status != "verified":
                out.append(year)
        except RatesError:
            out.append(year)
    return out


def ai_reader_on() -> bool:
    from .app_settings import load_app_settings

    return load_app_settings(current_app.config["SAWNX"]["settings"].tra_home).ai_reader


def register_context(app: Flask) -> None:
    @app.context_processor
    def _common():
        from .routes import income_years

        import getpass

        from .recent import recent_clients

        tra_home = current_app.config["SAWNX"]["settings"].tra_home
        try:
            recent = recent_clients(tra_home, getpass.getuser())
        except Exception:  # never let the recent list stop a page (or the error page) showing
            recent = []
        return {"rates_unverified": unverified_years(income_years()), "ai_reader_on": ai_reader_on(),
                "tra_home": str(tra_home), "recent_clients": recent}
