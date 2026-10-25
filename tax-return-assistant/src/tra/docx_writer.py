"""A small Word (.docx) writer, enough for a letter: a title, headings, tick-box items and plain text.

A .docx is a zip of a few XML files, so no extra library is needed. Every zip part gets the same fixed
timestamp, so the same letter is the same file byte for byte (and is filed once). The text is checked
by the output guard before anything is written.
"""

from __future__ import annotations

import io
import re
import zipfile
from pathlib import Path
from xml.sax.saxutils import escape

from .privacy.guard import atomic_write_bytes

STAMP = (2026, 1, 1, 0, 0, 0)
BOX = "☐ "
_CONTROL = re.compile(r"[\x00-\x08\x0b\x0c\x0e-\x1f]")
W = "http://schemas.openxmlformats.org/wordprocessingml/2006/main"
REL = "http://schemas.openxmlformats.org/package/2006/relationships"
HEAD = '<?xml version="1.0" encoding="UTF-8" standalone="yes"?>\n'

CONTENT_TYPES = HEAD + (
    '<Types xmlns="http://schemas.openxmlformats.org/package/2006/content-types">'
    '<Default Extension="rels" ContentType="application/vnd.openxmlformats-package.relationships+xml"/>'
    '<Default Extension="xml" ContentType="application/xml"/>'
    '<Override PartName="/word/document.xml" '
    'ContentType="application/vnd.openxmlformats-officedocument.wordprocessingml.document.main+xml"/>'
    '<Override PartName="/word/styles.xml" '
    'ContentType="application/vnd.openxmlformats-officedocument.wordprocessingml.styles+xml"/>'
    '</Types>')
PACKAGE_RELS = HEAD + (
    f'<Relationships xmlns="{REL}"><Relationship Id="rId1" '
    'Type="http://schemas.openxmlformats.org/officeDocument/2006/relationships/officeDocument" '
    'Target="word/document.xml"/></Relationships>')
DOCUMENT_RELS = HEAD + (
    f'<Relationships xmlns="{REL}"><Relationship Id="rId1" '
    'Type="http://schemas.openxmlformats.org/officeDocument/2006/relationships/styles" Target="styles.xml"/>'
    '</Relationships>')
STYLES = HEAD + (
    f'<w:styles xmlns:w="{W}">'
    '<w:docDefaults><w:rPrDefault><w:rPr><w:rFonts w:ascii="Calibri" w:hAnsi="Calibri" w:eastAsia="Calibri" '
    'w:cs="Calibri"/><w:sz w:val="22"/><w:lang w:val="en-AU"/></w:rPr></w:rPrDefault>'
    '<w:pPrDefault><w:pPr><w:spacing w:after="120" w:line="264" w:lineRule="auto"/></w:pPr></w:pPrDefault>'
    '</w:docDefaults>'
    '<w:style w:type="paragraph" w:default="1" w:styleId="Normal"><w:name w:val="Normal"/></w:style>'
    '<w:style w:type="paragraph" w:styleId="Title"><w:name w:val="Title"/><w:basedOn w:val="Normal"/>'
    '<w:next w:val="Normal"/><w:pPr><w:spacing w:after="240"/></w:pPr><w:rPr><w:b/><w:sz w:val="32"/></w:rPr>'
    '</w:style>'
    '<w:style w:type="paragraph" w:styleId="Heading1"><w:name w:val="heading 1"/><w:basedOn w:val="Normal"/>'
    '<w:next w:val="Normal"/><w:pPr><w:keepNext/><w:spacing w:before="240" w:after="80"/>'
    '<w:outlineLvl w:val="0"/></w:pPr><w:rPr><w:b/><w:sz w:val="26"/></w:rPr></w:style>'
    '</w:styles>')

_STYLE = {"title": '<w:pStyle w:val="Title"/>', "heading": '<w:pStyle w:val="Heading1"/>',
          "item": '<w:ind w:left="360" w:hanging="360"/>', "text": ""}


def _paragraph(style: str, text: str) -> str:
    if style not in _STYLE:
        raise ValueError(f"unknown paragraph style {style!r}")
    text = _CONTROL.sub("", text)  # Word refuses a file holding these
    shown = BOX + text if style == "item" else text
    props = f"<w:pPr>{_STYLE[style]}</w:pPr>" if _STYLE[style] else ""
    return f'<w:p>{props}<w:r><w:t xml:space="preserve">{escape(shown)}</w:t></w:r></w:p>'


def docx_bytes(paragraphs: list[tuple[str, str]]) -> bytes:
    body = "".join(_paragraph(style, text) for style, text in paragraphs)
    document = HEAD + (f'<w:document xmlns:w="{W}"><w:body>{body}'
                       '<w:sectPr><w:pgSz w:w="11906" w:h="16838"/>'
                       '<w:pgMar w:top="1440" w:right="1440" w:bottom="1440" w:left="1440" w:header="708" '
                       'w:footer="708" w:gutter="0"/></w:sectPr></w:body></w:document>')
    out = io.BytesIO()
    with zipfile.ZipFile(out, "w", zipfile.ZIP_DEFLATED) as z:
        for name, xml in (("[Content_Types].xml", CONTENT_TYPES), ("_rels/.rels", PACKAGE_RELS),
                          ("word/_rels/document.xml.rels", DOCUMENT_RELS), ("word/styles.xml", STYLES),
                          ("word/document.xml", document)):
            z.writestr(zipfile.ZipInfo(name, date_time=STAMP), xml.encode("utf-8"), zipfile.ZIP_DEFLATED)
    return out.getvalue()


def write_docx(path: Path, paragraphs: list[tuple[str, str]], location: str) -> None:
    atomic_write_bytes(path, docx_bytes(paragraphs), location, texts=[text for _style, text in paragraphs])
