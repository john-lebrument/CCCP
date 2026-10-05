import struct
from pathlib import Path
from typing import Dict, List, Any, Tuple, Optional
from PyQt6.QtCore import QFile, QDataStream, QIODevice


def _parse_tab_items(raw_bytes: bytes) -> List[Dict[str, bytes]]:
    """Parse raw CopyQ tab item binary data (QMap<QString, QByteArray> per item)."""
    off = 0

    def read_u32() -> int:
        nonlocal off
        val = struct.unpack(">I", raw_bytes[off:off + 4])[0]
        off += 4
        return val

    def read_u8() -> int:
        nonlocal off
        val = raw_bytes[off]
        off += 1
        return val

    if len(raw_bytes) < 4:
        return []

    num_items = read_u32()
    items = []

    for _ in range(num_items):
        if off >= len(raw_bytes):
            break
        tag = read_u32()
        num_mimes = read_u32() if tag == 0xFFFFFFFE else tag

        mimes: Dict[str, bytes] = {}
        for _ in range(num_mimes):
            if off + 4 > len(raw_bytes):
                break
            key_len = read_u32()
            if off + key_len > len(raw_bytes):
                break
            key = raw_bytes[off:off + key_len].decode("utf-16-be", errors="ignore").rstrip("\x00")
            off += key_len

            if off >= len(raw_bytes):
                break
            is_null = read_u8()

            if off + 4 > len(raw_bytes):
                break
            val_len = read_u32()
            if val_len == 0xFFFFFFFF:
                val_len = 0

            if off + val_len > len(raw_bytes):
                break
            val = raw_bytes[off:off + val_len]
            off += val_len

            mimes[key] = val

        items.append(mimes)

    return items


def _extract_text_and_title(mime_dict: Dict[str, bytes]) -> Tuple[str, str]:
    """Extract plain text and label/title from CopyQ item MIME dictionary."""
    content = ""

    # Check known plain text keys ('4' is CopyQ's default for text/plain)
    for k in ("4", "text/plain", "text/plain;charset=utf-8"):
        if k in mime_dict:
            try:
                content = mime_dict[k].decode("utf-8")
                break
            except Exception:
                try:
                    content = mime_dict[k].decode("latin-1")
                    break
                except Exception:
                    pass

    # If still empty, check HTML stripped or other text
    if not content:
        for k in ("5", "text/html"):
            if k in mime_dict:
                try:
                    raw_html = mime_dict[k].decode("utf-8", errors="ignore")
                    # Simple tag strip
                    import re
                    content = re.sub(r"<[^>]+>", "", raw_html).strip()
                    if content:
                        break
                except Exception:
                    pass

    # Title is usually '2' (CopyQ custom note / label)
    title = ""
    if "2" in mime_dict:
        try:
            title = mime_dict["2"].decode("utf-8").strip()
        except Exception:
            try:
                title = mime_dict["2"].decode("latin-1").strip()
            except Exception:
                pass

    content_clean = content.strip()
    if not title and content_clean:
        first_line = content_clean.split("\n")[0].strip()
        title = first_line[:40] if len(first_line) > 40 else first_line

    return title, content


def parse_copyq_export(file_path: str) -> Dict[str, Any]:
    """Parse a CopyQ .cpq export file and return categorized snippets and history."""
    qfile = QFile(file_path)
    if not qfile.open(QIODevice.OpenModeFlag.ReadOnly):
        raise IOError(f"Impossible d'ouvrir le fichier CopyQ : {file_path}")

    ds = QDataStream(qfile)
    magic = ds.readBytes()
    if magic != b"CopyQ v4":
        # Check if another version or invalid
        print(f"[CopyQ Importer] Warning: magic is {magic}")

    num_sections = ds.readInt32()
    # Read sections: commands, settings, tabs
    ds.readQString()
    ds.readQVariant()  # commands
    ds.readQString()
    ds.readQVariant()  # settings
    ds.readQString()
    tabs_list = ds.readQVariant()  # tabs

    tabs_data: Dict[str, List[Dict[str, bytes]]] = {}

    while not ds.atEnd():
        n = ds.readInt32()
        if ds.atEnd():
            break
        tab_meta = {}
        for _ in range(n):
            name = ds.readQString()
            ds.setVersion(QDataStream.Version.Qt_5_12)
            tab_meta[name] = ds.readQVariant()

        tab_name = tab_meta.get("name", "")
        raw_data = bytes(tab_meta.get("data", b""))
        if raw_data:
            items = _parse_tab_items(raw_data)
            tabs_data[tab_name] = items

    qfile.close()

    result = {
        "history": [],
        "folders": []
    }

    for raw_tab_name, items in tabs_data.items():
        clean_name = raw_tab_name.replace("&", "").strip()
        is_history = any(kw in clean_name.lower() for kw in ("presse-papier", "clipboard", "historique"))

        if is_history:
            for it in items:
                _, text = _extract_text_and_title(it)
                if text and text.strip():
                    result["history"].append(text)
        else:
            folder_snippets = []
            for it in items:
                title, text = _extract_text_and_title(it)
                if text and text.strip():
                    folder_snippets.append({
                        "name": title or "Extrait sans titre",
                        "content": text,
                        "shortcut": ""
                    })
            if folder_snippets:
                result["folders"].append({
                    "name": clean_name,
                    "snippets": folder_snippets
                })

    return result
