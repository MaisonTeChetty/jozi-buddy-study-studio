import hashlib
import json
import os
from pathlib import Path
import subprocess
import sys
import threading
import time
from uuid import uuid4
from collections import Counter

from .privacy import redact

PARSER_LOCK = threading.Semaphore(1)
ROOT = Path(__file__).resolve().parents[1]


def parse_pdf(data: bytes) -> dict:
    with PARSER_LOCK:
        process = subprocess.Popen([sys.executable, "-m", "studio.pdf_worker"], cwd=ROOT,
            stdin=subprocess.PIPE, stdout=subprocess.PIPE, stderr=subprocess.DEVNULL,
            creationflags=subprocess.CREATE_NO_WINDOW if os.name == "nt" else 0)
        job = None
        try:
            if os.name == "nt":
                import win32api
                import win32job
                job = win32job.CreateJobObject(None, "")
                limits = win32job.QueryInformationJobObject(job, win32job.JobObjectExtendedLimitInformation)
                limits["BasicLimitInformation"]["LimitFlags"] = win32job.JOB_OBJECT_LIMIT_PROCESS_MEMORY | win32job.JOB_OBJECT_LIMIT_KILL_ON_JOB_CLOSE
                limits["ProcessMemoryLimit"] = 384 * 1024 * 1024
                win32job.SetInformationJobObject(job, win32job.JobObjectExtendedLimitInformation, limits)
                handle = win32api.OpenProcess(0x0100 | 0x0001, False, process.pid)
                try:
                    win32job.AssignProcessToJobObject(job, handle)
                finally:
                    handle.Close()
            output, _ = process.communicate(data, timeout=20)
            if process.returncode or len(output) > 8 * 1024 * 1024:
                raise ValueError("The PDF exceeded safe processing limits.")
            result = json.loads(output)
            if not result.get("ok"):
                raise ValueError(result.get("error", "This PDF could not be processed."))
            return result
        except subprocess.TimeoutExpired:
            process.kill()
            process.communicate()
            raise ValueError("PDF processing timed out. Try a simpler document.") from None
        except (json.JSONDecodeError, OSError):
            raise ValueError("The isolated PDF parser could not complete.") from None
        finally:
            if process.poll() is None:
                process.kill()
                process.communicate()
            if job:
                job.Close()


def prepare_document(data: bytes, filename: str) -> dict:
    result = parse_pdf(data)
    identifier = str(uuid4())
    counts, chunks = Counter(), []
    for page in result["pages"]:
        page["text"], detected = redact(page["text"])
        counts.update(detected)
        if page["scanned"]:
            continue
        for offset in range(0, len(page["text"]), 1600):
            text = page["text"][offset:offset + 1800]
            chunks.append({"id": str(uuid4()), "page": page["page"], "text": text})
    return {"id": identifier, "title": filename[:-4], "filename": filename,
        "hash": hashlib.sha256(data).hexdigest(), "created": time.time(), "pages": result["pages"],
        "chunks": chunks, "redactions": dict(counts), "status": "indexing", "indexed": 0,
        "redaction_version": 1}


def summary(document):
    return {key: document[key] for key in ("id", "title", "filename", "created", "status", "indexed", "redactions")} | {
        "page_count": len(document["pages"]), "chunk_count": len(document["chunks"]),
        "scanned_pages": [page["page"] for page in document["pages"] if page["scanned"]],
        "error": document.get("error")}
