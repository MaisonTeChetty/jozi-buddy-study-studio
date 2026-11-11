"""Encrypted local records; encryption keys never enter the browser."""
from __future__ import annotations

import hashlib
import json
import os
from pathlib import Path
import secrets
import sqlite3
import time
from uuid import uuid4
from contextlib import contextmanager

from cryptography.hazmat.primitives.ciphers.aead import AESGCM


class Store:
    def __init__(self, directory: Path, key: bytes | None = None):
        directory.mkdir(parents=True, exist_ok=True)
        self.directory = directory
        self.dpapi_protected = key is None and os.name == "nt"
        if key is None:
            if os.name != "nt":
                raise RuntimeError("This release requires Windows DPAPI for protected storage.")
            import win32crypt
            key_path = directory / "protected-key.bin"
            if key_path.exists():
                key = win32crypt.CryptUnprotectData(key_path.read_bytes(), None, None, None, 0)[1]
            else:
                key = AESGCM.generate_key(bit_length=256)
                protected = win32crypt.CryptProtectData(key, "Jozi Buddy", None, None, None, 0)
                with key_path.open("xb") as output:
                    output.write(protected)
        self.cipher = AESGCM(key)
        self.database = directory / "studio.sqlite3"
        with self.connect() as connection:
            connection.executescript("""
                PRAGMA journal_mode=WAL;
                CREATE TABLE IF NOT EXISTS records (
                    kind TEXT NOT NULL, id TEXT NOT NULL, parent TEXT,
                    payload BLOB NOT NULL, created REAL NOT NULL,
                    PRIMARY KEY(kind,id));
                CREATE INDEX IF NOT EXISTS records_parent ON records(parent);
                CREATE TABLE IF NOT EXISTS usage (bucket TEXT PRIMARY KEY, value REAL NOT NULL);
            """)

    @contextmanager
    def connect(self):
        connection = sqlite3.connect(self.database, timeout=10)
        try:
            with connection:
                yield connection
        finally:
            connection.close()

    def replace_existing(self, kind, identifier, data):
        encrypted = self.seal(kind, identifier, json.dumps(data, ensure_ascii=False).encode())
        with self.connect() as connection:
            return connection.execute("UPDATE records SET payload=? WHERE kind=? AND id=?", (encrypted, kind, identifier)).rowcount > 0

    def seal(self, kind: str, identifier: str, data: bytes) -> bytes:
        nonce = secrets.token_bytes(12)
        return nonce + self.cipher.encrypt(nonce, data, f"{kind}:{identifier}".encode())

    def open(self, kind: str, identifier: str, data: bytes) -> bytes:
        return self.cipher.decrypt(data[:12], data[12:], f"{kind}:{identifier}".encode())

    def put_bytes(self, kind: str, identifier: str, data: bytes, parent: str | None = None, create=False):
        encrypted = self.seal(kind, identifier, data)
        with self.connect() as connection:
            if create:
                connection.execute("INSERT INTO records VALUES(?,?,?,?,?)", (kind, identifier, parent, encrypted, time.time()))
            else:
                connection.execute("""INSERT INTO records VALUES(?,?,?,?,?) ON CONFLICT(kind,id)
                    DO UPDATE SET payload=excluded.payload,parent=excluded.parent""",
                    (kind, identifier, parent, encrypted, time.time()))

    def get_bytes(self, kind: str, identifier: str) -> bytes | None:
        with self.connect() as connection:
            row = connection.execute("SELECT payload FROM records WHERE kind=? AND id=?", (kind, identifier)).fetchone()
        return self.open(kind, identifier, row[0]) if row else None

    def put(self, kind: str, identifier: str, data, parent: str | None = None, create=False):
        self.put_bytes(kind, identifier, json.dumps(data, ensure_ascii=False).encode(), parent, create)

    def put_child(self, kind, identifier, data, document_id):
        encrypted = self.seal(kind, identifier, json.dumps(data, ensure_ascii=False).encode())
        with self.connect() as connection:
            connection.execute("BEGIN IMMEDIATE")
            if not connection.execute("SELECT 1 FROM records WHERE kind='document' AND id=?", (document_id,)).fetchone():
                return False
            connection.execute("""INSERT INTO records VALUES(?,?,?,?,?) ON CONFLICT(kind,id)
                DO UPDATE SET payload=excluded.payload,parent=excluded.parent""",
                (kind, identifier, document_id, encrypted, time.time()))
            return True

    def mutate(self, kind, identifier, change):
        """Apply a short record transformation atomically across local processes."""
        with self.connect() as connection:
            connection.execute("BEGIN IMMEDIATE")
            row = connection.execute("SELECT payload FROM records WHERE kind=? AND id=?", (kind, identifier)).fetchone()
            value = json.loads(self.open(kind, identifier, row[0])) if row else None
            replacement, result = change(value)
            if row and replacement is not None:
                encrypted = self.seal(kind, identifier, json.dumps(replacement, ensure_ascii=False).encode())
                connection.execute("UPDATE records SET payload=? WHERE kind=? AND id=?", (encrypted, kind, identifier))
            return result

    def get(self, kind: str, identifier: str):
        data = self.get_bytes(kind, identifier)
        return json.loads(data) if data is not None else None

    def list(self, kind: str, parent: str | None = None, limit=100):
        with self.connect() as connection:
            if parent is None:
                rows = connection.execute("SELECT id,payload FROM records WHERE kind=? ORDER BY created DESC LIMIT ?", (kind, limit)).fetchall()
            else:
                rows = connection.execute("SELECT id,payload FROM records WHERE kind=? AND parent=? ORDER BY created DESC LIMIT ?", (kind, parent, limit)).fetchall()
        return [json.loads(self.open(kind, identifier, payload)) for identifier, payload in rows]

    def delete(self, kind: str, identifier: str):
        with self.connect() as connection:
            connection.execute("DELETE FROM records WHERE kind=? AND id=?", (kind, identifier))

    def delete_document(self, identifier: str):
        with self.connect() as connection:
            connection.execute("DELETE FROM records WHERE parent=? OR (kind IN ('document','pdf') AND id=?)", (identifier, identifier))

    def consume(self, bucket: str, limit: float, amount=1.0) -> bool:
        with self.connect() as connection:
            connection.execute("BEGIN IMMEDIATE")
            row = connection.execute("SELECT value FROM usage WHERE bucket=?", (bucket,)).fetchone()
            current = row[0] if row else 0
            if current + amount > limit:
                return False
            connection.execute("INSERT INTO usage VALUES(?,?) ON CONFLICT(bucket) DO UPDATE SET value=excluded.value", (bucket, current + amount))
        return True

    def used(self, bucket: str) -> float:
        with self.connect() as connection:
            row = connection.execute("SELECT value FROM usage WHERE bucket=?", (bucket,)).fetchone()
        return row[0] if row else 0

    def audit(self, event: str, decision="allowed", reason="", document_id: str | None = None):
        identifier = str(uuid4())
        self.put("audit", identifier, {"id": identifier, "event": event, "decision": decision,
            "reason": reason, "document_id": document_id, "timestamp": time.time()})


def digest(value: str) -> str:
    return hashlib.sha256(value.encode()).hexdigest()
