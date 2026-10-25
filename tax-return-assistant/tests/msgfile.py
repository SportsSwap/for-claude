"""Write small made-up Outlook .msg files for tests (olefile only reads them).

A .msg is a compound file: a directory of storages and streams. This writes version 3: 512-byte
sectors, and streams under 4096 bytes in the mini stream (64-byte mini sectors), as the format
requires. Siblings are a simple right-hand chain.
"""

from __future__ import annotations

import struct
from datetime import datetime, timezone

SECTOR = 512
ATTACH_DATA = "__substg1.0_" + "3701" + "0102"  # those 8 digits pass the TFN check; never written whole
MINI = 64
CUTOFF = 4096
FREE, END, FATSECT, NOSTREAM = 0xFFFFFFFF, 0xFFFFFFFE, 0xFFFFFFFD, 0xFFFFFFFF


def _utf16(text: str) -> bytes:
    return text.encode("utf-16-le")


def _filetime(when: datetime) -> int:
    epoch = datetime(1601, 1, 1, tzinfo=timezone.utc)
    return int((when.astimezone(timezone.utc) - epoch).total_seconds() * 10_000_000)


def _properties(header: int, props: list[tuple[int, int, bytes]]) -> bytes:
    """A property stream: header bytes, then 16-byte entries (tag, flags, 8-byte value)."""
    out = b"\0" * header
    for prop_id, prop_type, value in props:
        out += struct.pack("<II", (prop_id << 16) | prop_type, 6) + value.ljust(8, b"\0")
    return out


def message_tree(subject: str, body: str = "", *, html: bytes | None = None, sent: datetime | None = None,
                 attachments: list[tuple[str, bytes]] = (), embedded: list[dict] = (),
                 inline_images: list[tuple[str, bytes]] = (), links: list[str] = (), rtf: bytes | None = None,
                 top: bool = True) -> dict:
    """A message as {name: bytes | {...}}: streams are bytes, storages are dicts."""
    tree: dict = {"__substg1.0_0037001F": _utf16(subject)}
    if body:
        tree["__substg1.0_1000001F"] = _utf16(body)
    if html is not None:
        tree["__substg1.0_10130102"] = html
    if rtf is not None:
        tree["__substg1.0_10090102"] = rtf  # compressed RTF body, which olefile can't decode
    props = [(0x0039, 0x0040, struct.pack("<Q", _filetime(sent)))] if sent else []
    tree["__properties_version1.0"] = _properties(32 if top else 24, props)
    n = 0
    for name, data in attachments:
        tree[f"__attach_version1.0_#{n:08X}"] = {ATTACH_DATA: data, "__substg1.0_3707001F": _utf16(name),
                                                  "__properties_version1.0": _properties(8, [])}
        n += 1
    for name, data in inline_images:
        tree[f"__attach_version1.0_#{n:08X}"] = {ATTACH_DATA: data, "__substg1.0_3707001F": _utf16(name),
                                                  "__substg1.0_3712001F": _utf16("logo@sample"),
                                                  "__properties_version1.0": _properties(8, [])}
        n += 1
    for name in links:  # an attachment by reference (a OneDrive link): a name but no data
        tree[f"__attach_version1.0_#{n:08X}"] = {"__substg1.0_3707001F": _utf16(name),
                                                  "__properties_version1.0": _properties(8, [])}
        n += 1
    for inner in embedded:
        tree[f"__attach_version1.0_#{n:08X}"] = {"__substg1.0_3701000D": message_tree(**inner, top=False),
                                                  "__properties_version1.0": _properties(
                                                      8, [(0x3705, 0x0003, struct.pack("<I", 5))])}
        n += 1
    return tree


def write_compound(path, tree: dict) -> None:
    entries = [{"name": "Root Entry", "type": 5, "data": b"", "kids": []}]

    def add(node: dict, parent: int) -> None:
        for name, value in node.items():
            entries.append({"name": name, "type": 1 if isinstance(value, dict) else 2,
                            "data": b"" if isinstance(value, dict) else value, "kids": []})
            me = len(entries) - 1
            entries[parent]["kids"].append(me)
            if isinstance(value, dict):
                add(value, me)

    add(tree, 0)
    sectors: list[bytes] = []
    fat: list[int] = []

    def place(data: bytes) -> int:
        if not data:
            return END
        first = len(sectors)
        chunks = [data[i:i + SECTOR] for i in range(0, len(data), SECTOR)]
        for i, chunk in enumerate(chunks):
            sectors.append(chunk.ljust(SECTOR, b"\0"))
            fat.append(first + i + 1 if i + 1 < len(chunks) else END)
        return first

    mini, minifat = b"", []
    for e in entries:
        if e["type"] != 2 or not e["data"]:
            e["start"] = END
        elif len(e["data"]) >= CUTOFF:
            e["start"] = place(e["data"])
        else:
            e["start"] = len(minifat)
            count = -(-len(e["data"]) // MINI)
            mini += e["data"].ljust(count * MINI, b"\0")
            minifat += [e["start"] + i + 1 if i + 1 < count else END for i in range(count)]
    root_size = len(mini)
    entries[0]["start"] = place(mini) if mini else END
    entries[0]["size"] = root_size
    minifat_bytes = struct.pack(f"<{len(minifat)}I", *minifat) if minifat else b""
    minifat_bytes += struct.pack("<I", FREE) * ((-len(minifat_bytes) % SECTOR) // 4)
    minifat_start = place(minifat_bytes) if minifat_bytes else END
    minifat_count = len(minifat_bytes) // SECTOR
    directory = b""
    for e in entries:
        kids = e["kids"]
        e["child"] = kids[0] if kids else NOSTREAM
        for a, b in zip(kids, kids[1:] + [None]):
            entries[a]["right"] = b if b is not None else NOSTREAM
    for e in entries:
        name = _utf16(e["name"]) + b"\0\0"
        directory += (name.ljust(64, b"\0") + struct.pack("<HBB", len(name), e["type"], 1)
                      + struct.pack("<III", NOSTREAM, e.get("right", NOSTREAM), e["child"])
                      + b"\0" * 16 + b"\0" * 4 + b"\0" * 16
                      + struct.pack("<IQ", e["start"], e.get("size", len(e["data"]))))
    dir_start = place(directory.ljust(-(-len(directory) // SECTOR) * SECTOR, b"\0"))
    fat_sectors = 1
    while (len(fat) + fat_sectors) > fat_sectors * (SECTOR // 4):
        fat_sectors += 1
    fat_start = len(sectors)
    fat += [FATSECT] * fat_sectors
    fat += [FREE] * (fat_sectors * (SECTOR // 4) - len(fat))
    fat_bytes = struct.pack(f"<{len(fat)}I", *fat)
    sectors += [fat_bytes[i:i + SECTOR] for i in range(0, len(fat_bytes), SECTOR)]
    difat = [fat_start + i for i in range(fat_sectors)] + [FREE] * (109 - fat_sectors)
    header = (b"\xD0\xCF\x11\xE0\xA1\xB1\x1A\xE1" + b"\0" * 16
              + struct.pack("<HHHHH", 0x3E, 3, 0xFFFE, 9, 6) + b"\0" * 6
              + struct.pack("<IIIIIIIII", 0, fat_sectors, dir_start, 0, CUTOFF, minifat_start, minifat_count,
                            END, 0)
              + struct.pack("<109I", *difat))
    with open(path, "wb") as fh:
        fh.write(header.ljust(SECTOR, b"\0"))
        fh.writelines(sectors)


def write_msg(path, subject: str, body: str = "", **kwargs) -> None:
    write_compound(path, message_tree(subject, body, **kwargs))
