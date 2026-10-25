"""Record ids Sawnx makes up must never look like a TFN, Medicare or card number.

The output guard scans every saved value, ids included. Hex ids from
``secrets.token_hex`` sometimes held a run of digits that passed the TFN
check digit, and the save was refused (about 1 note in 220).
"""

import secrets
from datetime import date

from webctx import make_client, new_client

from tra.demo import _write_pdf
from tra.privacy.audit import AuditLog
from tra.privacy.detectors import find_sensitive
from tra.web.client_notes import add_note
from tra.web.comments import add_comment
from tra.web.ids import new_id
from tra.web.intray import add_to_tray
from tra.web.jobs import add_job, add_task
from tra.web.rules import add_rule
from tra.web.timesheet import add_time


def test_new_ids_have_no_digits():
    ids = [new_id() for _ in range(5000)]
    assert all(len(i) == 12 and i.isascii() and i.isalpha() and i.islower() for i in ids)
    assert not [i for i in ids if find_sensitive(i)]
    assert len(set(ids)) == len(ids)
    assert len(new_id(10)) == 10


def _unlucky_token_hex(monkeypatch, make_tfn, make_card):
    """Make ``secrets.token_hex`` return what it can return by chance: hex the guard refuses."""
    def fake(nbytes=32):
        width = 2 * nbytes
        if width >= 16:  # hex this long with a letter is masked as a hash; all digits is not
            return make_card(width)
        pad = "a" * (width - 8)
        return pad[:len(pad) // 2] + make_tfn(8) + pad[len(pad) // 2:]
    monkeypatch.setattr(secrets, "token_hex", fake)


def test_records_save_whatever_the_random_draw(tmp_path, monkeypatch, make_tfn, make_card):
    _app, _client, settings = make_client(tmp_path, monkeypatch)
    new_client(settings)
    home, audit = settings.tra_home, AuditLog(tmp_path / "a.jsonl")
    pdf = tmp_path / "letter.pdf"
    _write_pdf(pdf, ["Letter from the client", "Dated 1 March 2026"])
    _unlucky_token_hex(monkeypatch, make_tfn, make_card)

    note = add_note(home, "TEST01", "Client called about the dividend statement.", "nicho")
    job = add_job(home, "TEST01", "BAS Q1", due="", assignee="", notes="", by="nicho", audit=audit)
    task = add_task(home, "Chase the receipts", job_id=job.id, due="", assignee="", by="nicho", audit=audit)
    comment = add_comment(home, "TEST01", f"job:{job.id}", "Waiting on the client", "nicho", audit)
    entry = add_time(home, job.id, date.today().isoformat(), "30", "Checked figures", "nicho", audit)
    rule = add_rule(home, "Harbour Accounting Trust", "TEST01", "Permanent", "Trust deeds", audit)
    item = add_to_tray(home, pdf, "nicho", audit)

    ids = [note["id"], job.id, task.id, comment["id"], entry["id"], rule["id"], item.id]
    assert not [i for i in ids if any(c.isdigit() for c in i)]
