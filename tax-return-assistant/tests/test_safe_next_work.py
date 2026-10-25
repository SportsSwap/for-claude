"""The jobs and tasks pages send people back only to a page on this site (same rule as home_routes)."""

import pytest

from tra.web.work_routes import _safe_next


@pytest.mark.parametrize("bad", ["//evil.example", r"/\evil.example", r"\\evil.example", "https://evil.example", ""])
def test_other_sites_refused(bad):
    assert _safe_next(bad) == "/"


def test_own_pages_kept():
    assert _safe_next("/jobs/abc?x=1") == "/jobs/abc?x=1"
