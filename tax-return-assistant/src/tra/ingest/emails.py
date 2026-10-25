"""Emails: .eml (Python's email package) and Outlook .msg (olefile).

read_email gives the subject, sent time, body and attachments. Raw text from here goes only to
readers.load, which redacts it at once; attachments go back through the normal ingest as their own
documents. The sender, recipients and attachment file names are never kept: an attachment is just
its file type and bytes. Signature logos and other inline pictures are skipped.
"""

from __future__ import annotations

import email
import email.policy
import mimetypes
import re
import struct
from dataclasses import dataclass, field
from datetime import datetime, timedelta, timezone
from email.utils import parsedate_to_datetime
from html.parser import HTMLParser
from pathlib import Path

MAX_ATTACHMENTS = 20
EMAIL_TYPES = (".eml", ".msg")
_IMAGES = (".png", ".jpg", ".jpeg", ".gif", ".bmp")
# A picture shown in the message itself smaller than this is taken to be a logo; a bigger one (a phone photo of a
# receipt, which iPhones send inline) is kept as an attachment.
INLINE_PHOTO_MIN = 30_000
EMBEDDED_SKIPPED = "An email attached inside this one couldn't be read. Save it from Outlook on its own and import it."
# Outlook's attachment-data stream: property 0x3701, type 0x0102. Built from two halves because those 8 digits
# happen to pass the TFN check digit, and no such run may appear in a committed file (tests/test_repo_hygiene.py).
ATTACH_DATA = "__substg1.0_" + "3701" + "0102"
RTF_SKIPPED = "The email's text is in a format Sawnx can't read (rich text). Open the email and check it."


@dataclass
class Attachment:
    suffix: str
    data: bytes


@dataclass
class EmailContent:
    subject: str
    sent: datetime | None
    body: str
    attachments: list[Attachment] = field(default_factory=list)
    skipped: list[str] = field(default_factory=list)


class _Text(HTMLParser):
    """HTML to plain lines: block tags start a new line; scripts and styles are dropped."""

    BLOCKS = {"br", "p", "div", "tr", "li", "h1", "h2", "h3", "h4", "h5", "h6", "table", "ul", "ol"}

    def __init__(self):
        super().__init__(convert_charrefs=True)
        self.out: list[str] = []
        self.hidden = 0

    def handle_starttag(self, tag, attrs):
        if tag in ("script", "style", "head"):
            self.hidden += 1
        elif tag in self.BLOCKS:
            self.out.append("\n")
        elif tag in ("td", "th"):
            self.out.append(" ")  # cells pasted from Excel: keep "Donation" and "$500" apart

    def handle_endtag(self, tag):
        if tag in ("script", "style", "head"):
            self.hidden = max(0, self.hidden - 1)
        elif tag in self.BLOCKS:
            self.out.append("\n")

    def handle_data(self, data):
        if not self.hidden:
            self.out.append(data.replace("\xa0", " "))


def html_to_text(html: str) -> str:
    parser = _Text()
    parser.feed(html)
    parser.close()
    lines = [" ".join(line.split()) for line in "".join(parser.out).splitlines()]
    return re.sub(r"\n{3,}", "\n\n", "\n".join(lines)).strip()


def _limit(content: EmailContent, attachments: list[Attachment]) -> EmailContent:
    if len(attachments) > MAX_ATTACHMENTS:
        content.skipped.append(f"Only the first {MAX_ATTACHMENTS} attachments were read; "
                               f"{len(attachments) - MAX_ATTACHMENTS} more weren't.")
    content.attachments = attachments[:MAX_ATTACHMENTS]
    return content


# --- .eml ---------------------------------------------------------------------------------------

def _leaves(part):
    if part.get_content_type() == "message/rfc822":
        yield part
    elif part.is_multipart():
        for sub in part.iter_parts():
            yield from _leaves(sub)
    else:
        yield part


def _suffix(filename: str | None, content_type: str) -> str:
    suffix = Path(filename).suffix.lower() if filename else ""
    return suffix or (mimetypes.guess_extension(content_type) or "")


def _read_eml(path: Path) -> EmailContent:
    msg = email.message_from_bytes(path.read_bytes(), policy=email.policy.default)
    try:
        sent = parsedate_to_datetime(str(msg["date"])) if msg["date"] else None
    except (TypeError, ValueError):
        sent = None
    body_part = msg.get_body(preferencelist=("plain", "html"))
    body = _text_of(body_part) if body_part is not None else ""
    if body_part is not None and body_part.get_content_type() == "text/html":
        body = html_to_text(body)
    attachments = []
    for part in _leaves(msg):
        if part is body_part:
            continue
        ctype, disposition, filename = part.get_content_type(), part.get_content_disposition(), part.get_filename()
        if ctype == "message/rfc822":
            inner = part.get_payload(0) if part.is_multipart() else part.get_content()
            attachments.append(Attachment(".eml", inner.as_bytes()))
            continue
        data = part.get_payload(decode=True) or b""
        if part.get_content_maintype() == "image" and disposition != "attachment" and (
                part["Content-ID"] or disposition == "inline") and len(data) < INLINE_PHOTO_MIN:
            continue  # a signature logo or other small picture in the message itself
        if ctype in ("text/plain", "text/html") and not filename and disposition != "attachment":
            continue  # the other version of the body
        attachments.append(Attachment(_suffix(filename, ctype), data))
    return _limit(EmailContent(str(msg["subject"] or ""), sent, body), attachments)


def _text_of(part) -> str:
    """A body part's text; one in a character set Python doesn't know is read as UTF-8 with stand-ins."""
    try:
        return part.get_content()
    except (LookupError, UnicodeDecodeError):
        return (part.get_payload(decode=True) or b"").decode("utf-8", errors="replace")


# --- .msg ---------------------------------------------------------------------------------------

def _filetime(raw: bytes) -> datetime | None:
    (value,) = struct.unpack("<Q", raw)
    if not value:
        return None
    return datetime(1601, 1, 1, tzinfo=timezone.utc) + timedelta(microseconds=value // 10)


class _Msg:
    def __init__(self, ole, prefix: str = ""):
        self.ole, self.prefix = ole, prefix

    def stream(self, name: str) -> bytes | None:
        full = self.prefix + name
        return self.ole.openstream(full).read() if self.ole.exists(full) else None

    def text(self, prop: str) -> str:
        unicode = self.stream(f"__substg1.0_{prop}001F")
        if unicode is not None:
            return unicode.decode("utf-16-le", errors="replace").rstrip("\x00")
        ansi = self.stream(f"__substg1.0_{prop}001E")
        return ansi.decode("cp1252", errors="replace").rstrip("\x00") if ansi is not None else ""

    def sent(self, header: int) -> datetime | None:
        props = self.stream("__properties_version1.0") or b""
        for at in range(header, len(props) - 15, 16):
            tag = struct.unpack("<I", props[at:at + 4])[0]
            if tag == (0x0039 << 16) | 0x0040:
                return _filetime(props[at + 8:at + 16])
        return None


class EmailLibraryMissing(Exception):
    """olefile isn't installed (a laptop set up before .msg files could be read)."""


def _read_msg(path: Path) -> EmailContent:
    try:
        import olefile
    except ImportError:
        raise EmailLibraryMissing("Reading Outlook .msg files needs an update: close Sawnx, then in PowerShell in "
                                  "the tool's folder run  .venv\\Scripts\\pip install -e .  and start Sawnx again. "
                                  "Or save the email as .eml and import that.") from None

    with olefile.OleFileIO(str(path)) as ole:
        msg = _Msg(ole)
        body = msg.text("1000")
        if not body.strip():
            html = msg.stream("__substg1.0_10130102")
            body = html_to_text(html.decode("utf-8", errors="replace")) if html else html_to_text(msg.text("1013"))
        content = EmailContent(msg.text("0037"), msg.sent(32), body)
        if not body.strip() and msg.stream("__substg1.0_10090102") is not None:
            content.skipped.append(RTF_SKIPPED)
        storages = sorted({entry[0] for entry in ole.listdir(streams=True, storages=True)
                           if entry[0].startswith("__attach_version1.0_#")})
        attachments = []
        for number, storage in enumerate(storages, start=1):
            part = _Msg(ole, storage + "/")
            if ole.exists(storage + "/__substg1.0_3701000D"):
                content.skipped.append(EMBEDDED_SKIPPED)
                continue
            data = part.stream(ATTACH_DATA)
            if data is None:
                content.skipped.append(f"Attachment {number} is a link (for example to OneDrive), not a file. "
                                       "Open the email to get it.")
                continue
            name = part.text("3707") or part.text("3704")
            suffix = Path(name).suffix.lower() if name else part.text("3703").lower()
            if part.text("3712") and suffix in _IMAGES and len(data) < INLINE_PHOTO_MIN:
                continue  # a small picture shown in the message (a signature logo)
            attachments.append(Attachment(suffix, data))
    return _limit(content, attachments)


def read_email(path: Path) -> EmailContent:
    return _read_msg(path) if path.suffix.lower() == ".msg" else _read_eml(path)


def email_page_text(content: EmailContent) -> str:
    """The text that is read (and redacted): subject, date and body. Not the sender or recipients."""
    when = content.sent.strftime("%d/%m/%Y") if content.sent else ""
    return f"Subject: {content.subject}\nDate: {when}\n\n{content.body}"
