"""Isolated PDF parsing process. Input/output are pipes, never uploaded paths."""
import io
import json
import sys

from pypdf import PdfReader
from pypdf.generic import ArrayObject, DictionaryObject, IndirectObject

FORBIDDEN = {"/JS", "/JavaScript", "/Launch", "/EmbeddedFiles", "/EmbeddedFile", "/OpenAction", "/AA", "/RichMedia"}


def extract(data: bytes) -> dict:
    if len(data) > 10 * 1024 * 1024 or not data.startswith(b"%PDF-"):
        raise ValueError("Upload a PDF smaller than 10 MiB.")
    reader = PdfReader(io.BytesIO(data), strict=True)
    if reader.is_encrypted:
        raise ValueError("Password-protected PDFs are not supported. Upload an unencrypted copy.")
    if not 1 <= len(reader.pages) <= 100:
        raise ValueError("PDFs must contain between 1 and 100 pages.")
    visited = set()
    nodes = 0

    def inspect(value):
        nonlocal nodes
        nodes += 1
        if nodes > 100000:
            raise ValueError("This PDF is too complex to process safely.")
        if isinstance(value, IndirectObject):
            key = (value.idnum, value.generation)
            if key in visited:
                return
            visited.add(key)
            value = value.get_object()
        if isinstance(value, DictionaryObject):
            if FORBIDDEN.intersection(str(key) for key in value.keys()) or str(value.get("/S", "")) in FORBIDDEN:
                raise ValueError("Embedded scripts, actions, or attachments are not allowed.")
            for item in value.values():
                inspect(item)
        elif isinstance(value, ArrayObject):
            for item in value:
                inspect(item)

    inspect(reader.trailer)
    pages, total = [], 0
    for index, page in enumerate(reader.pages, 1):
        text = (page.extract_text() or "").strip()
        total += len(text)
        if total > 1000000:
            raise ValueError("The extracted document is too large for this release.")
        pages.append({"page": index, "text": text, "scanned": len(text) < 10})
    if all(page["scanned"] for page in pages):
        raise ValueError("This PDF has no readable text. OCR for scanned PDFs is not available yet.")
    return {"pages": pages}


if __name__ == "__main__":
    # Parser diagnostics can contain source content. Keep stderr out of app logs.
    try:
        result = extract(sys.stdin.buffer.read(10 * 1024 * 1024 + 1))
        print(json.dumps({"ok": True, **result}))
    except ValueError as error:
        print(json.dumps({"ok": False, "error": str(error) if type(error) is ValueError else "This PDF could not be parsed safely."}))
    except Exception:
        print(json.dumps({"ok": False, "error": "This PDF could not be parsed safely."}))
