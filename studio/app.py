"""Loopback-only API for the authenticated study studio."""
from __future__ import annotations

import asyncio
from contextlib import asynccontextmanager
import hashlib
import io
import json
import os
from pathlib import Path
import secrets
import sqlite3
import time
from urllib.parse import unquote
from uuid import uuid4

from fastapi import BackgroundTasks, FastAPI, HTTPException, Request, Response, WebSocket
from fastapi.exceptions import RequestValidationError
from fastapi.responses import FileResponse, JSONResponse, StreamingResponse
from starlette.middleware.base import BaseHTTPMiddleware
from starlette.staticfiles import StaticFiles
import pyotp

from name_memory import NameMemory, validate_name
from .ai import AI, DEFAULT_LIMITS, day
from .auth import Auth, hasher
from .documents import prepare_document, summary
from .exports import export_quiz
from .privacy import redact, redact_data
from .schemas import (AskInput, CodeInput, GenerateInput, LimitsInput, LoginInput, MFAOff,
    NarrateInput, PasswordInput, ProfileInput, QuizDraft, StartAttempt, SubmitAnswer)
from .storage import Store, digest
from . import responses as out

ROOT = Path(__file__).resolve().parents[1]
ORIGINS = {f"http://{host}:{port}" for host in ("127.0.0.1", "localhost") for port in (8765, 8766, 5173)}
PUBLIC_QUESTION_FIELDS = {"id", "type", "prompt", "options", "marks", "pages", "needs_review"}


class BoundaryMiddleware(BaseHTTPMiddleware):
    async def dispatch(self, request, call_next):
        host = request.headers.get("host", "").split(":")[0].lower()
        if host not in {"127.0.0.1", "localhost"}:
            return JSONResponse({"detail": "This app accepts local requests only."}, status_code=400)
        origin = request.headers.get("origin")
        if origin and origin not in ORIGINS:
            request.app.state.store.audit("origin_check", "blocked", "untrusted_origin")
            return JSONResponse({"detail": "This origin is not allowed."}, status_code=403)
        if request.method not in {"GET", "HEAD", "OPTIONS"} and request.headers.get("sec-fetch-site") == "cross-site":
            return JSONResponse({"detail": "Cross-site requests are not allowed."}, status_code=403)
        try:
            if int(request.headers.get("content-length", "0")) > 11 * 1024 * 1024:
                return JSONResponse({"detail": "The upload exceeds 10 MiB."}, status_code=413)
        except ValueError:
            return JSONResponse({"detail": "Invalid request size."}, status_code=400)
        if request.method in {"POST", "PUT", "PATCH", "DELETE"} and request.url.path != "/api/v1/documents":
            body = bytearray()
            async for piece in request.stream():
                body.extend(piece)
                if len(body) > 64 * 1024:
                    return JSONResponse({"detail": "This request exceeds the 64 KiB limit."}, status_code=413)
            # Starlette's cached request replays this bounded body to FastAPI.
            request._body = bytes(body)
        response = await call_next(request)
        response.headers.update({
            "Content-Security-Policy": "default-src 'self'; script-src 'self'; style-src 'self' 'unsafe-inline'; img-src 'self' data: blob:; font-src 'self' data:; connect-src 'self' ws://127.0.0.1:8765 ws://localhost:8765 ws://127.0.0.1:8766; worker-src 'self' blob:; object-src 'none'; frame-ancestors 'none'; base-uri 'self'; form-action 'self'",
            "X-Content-Type-Options": "nosniff", "X-Frame-Options": "DENY", "Referrer-Policy": "no-referrer",
            "Permissions-Policy": "microphone=(self), camera=(), geolocation=()",
            "Cache-Control": "no-store" if request.url.path.startswith("/api") else "no-cache",
        })
        return response


def create_app(data_dir: Path | None = None, *, store: Store | None = None, ai: AI | None = None):
    directory = data_dir or Path(os.environ.get("JOZI_STUDIO_DATA_DIR", str(Path(os.environ.get("LOCALAPPDATA", Path.home())) / "JoziBuddy")))
    store = store or Store(directory)
    auth = Auth(store)
    ai = ai or AI(store)
    @asynccontextmanager
    async def lifespan(application):
        for pending in store.list("document", limit=10000):
            if pending["status"] == "indexing":
                pending["status"] = "needs_aws"
                pending["error"] = "Indexing was interrupted. Retry indexing to finish the saved passages."
                store.replace_existing("document", pending["id"], pending)
        yield
    app = FastAPI(title="Jozi Buddy Study Studio", version="1.0.0", docs_url=None, redoc_url=None, openapi_url=None, lifespan=lifespan)
    app.state.store, app.state.auth, app.state.ai = store, auth, ai
    app.state.voice_lock = asyncio.Lock()
    app.add_middleware(BoundaryMiddleware)

    @app.exception_handler(RequestValidationError)
    async def invalid_input(request, error):
        # FastAPI's default response echoes invalid values, including passwords.
        return JSONResponse({"detail": "Check the highlighted fields and try again.",
            "fields": [".".join(map(str, issue["loc"][1:])) for issue in error.errors()]}, status_code=422)

    @app.exception_handler(Exception)
    async def unexpected_error(request, error):
        store.audit("application_error", "failed", type(error).__name__)
        return JSONResponse({"detail": "Something went wrong. Your saved work is safe; please try again."}, status_code=500)

    def document(identifier):
        value = store.get("document", identifier)
        if value is None:
            raise HTTPException(404, "That document is not available.")
        return value

    def quiz(identifier):
        value = store.get("quiz", identifier)
        if value is None:
            raise HTTPException(404, "That question set is not available.")
        return value

    def attempt(identifier):
        value = store.get("attempt", identifier)
        if value is None:
            raise HTTPException(404, "That attempt is not available.")
        return value

    def save_child(kind, identifier, value, document_id):
        if not store.put_child(kind, identifier, value, document_id):
            raise HTTPException(404, "The source document was removed. This result was not saved.")

    def public_attempt(value):
        result = {key: item for key, item in value.items() if key not in {"questions", "grades"}}
        result["questions"] = [{key: item for key, item in question.items() if key in PUBLIC_QUESTION_FIELDS} for question in value["questions"]]
        result["grades"] = value["grades"] if value["mode"] == "practice" or value["submitted"] else {}
        result["total_marks"] = sum(question["marks"] for question in value["questions"])
        result["score"] = sum(grade["score"] for grade in result["grades"].values())
        return result

    @app.get("/api/v1/health", response_model=out.Health)
    def health():
        return {"status": "ok", "app": "Jozi Buddy Study Studio"}

    @app.get("/api/v1/auth/status", response_model=out.AuthStatus)
    def auth_status(request: Request, response: Response):
        owner = store.get("owner", "owner")
        try:
            session = auth.session(request, ("owner", "guest", "pending"))
            result = {"authenticated": session["kind"] == "owner", "csrf": session["csrf"], "mfa_required": session["kind"] == "pending"}
        except HTTPException:
            if not store.consume(f"guest:{int(time.time() // 60)}", 60):
                raise HTTPException(429, "Please wait a moment before refreshing sign-in.")
            result = auth.issue(response, "guest")
        return result | {"setup_required": owner is None, "mfa_enabled": bool(owner and owner.get("totp_secret")), "profile": store.get("profile", "owner") if result["authenticated"] else None}

    @app.post("/api/v1/auth/setup", response_model=out.AuthStatus)
    def setup(body: PasswordInput, request: Request, response: Response):
        auth.mutation(request, ("guest",))
        auth.throttle(request)
        try:
            store.put("owner", "owner", {"password": hasher.hash(body.password.get_secret_value())}, create=True)
        except sqlite3.IntegrityError:
            raise HTTPException(409, "The owner account has already been created.") from None
        try:
            name = NameMemory().load_name()
        except OSError:
            name = None
        store.put("profile", "owner", {"name": name})
        auth.revoke(request)
        store.audit("owner_created")
        return auth.issue(response)

    @app.post("/api/v1/auth/login", response_model=out.AuthStatus)
    def login(body: LoginInput, request: Request, response: Response):
        auth.mutation(request, ("guest", "pending"))
        auth.throttle(request)
        if not auth.password(body.password.get_secret_value()):
            store.audit("login", "blocked", "invalid_credentials")
            raise HTTPException(401, "Those sign-in details did not match.")
        owner = store.get("owner", "owner")
        auth.revoke(request)
        store.audit("password_verified")
        return auth.issue(response, "pending" if owner.get("totp_secret") else "owner")

    @app.post("/api/v1/auth/verify", response_model=out.AuthStatus)
    def verify(body: CodeInput, request: Request, response: Response):
        auth.mutation(request, ("pending",))
        auth.throttle(request)
        if not auth.verify_code(body.code, store.get("owner", "owner")):
            store.audit("mfa_verify", "blocked", "invalid_code")
            raise HTTPException(401, "That code did not match, or it has already been used.")
        auth.revoke(request)
        store.audit("login", "allowed", "mfa_verified")
        return auth.issue(response)

    @app.post("/api/v1/auth/logout", response_model=out.Operation)
    def logout(request: Request, response: Response):
        auth.mutation(request)
        auth.revoke(request)
        response.delete_cookie("jb_session", path="/")
        store.audit("logout")
        return {"ok": True}

    @app.post("/api/v1/auth/mfa/setup", response_model=out.MFASetup)
    def mfa_setup(body: PasswordInput, request: Request):
        auth.mutation(request)
        auth.throttle(request)
        if not auth.password(body.password.get_secret_value()):
            raise HTTPException(401, "Those sign-in details did not match.")
        owner = store.get("owner", "owner")
        if owner.get("totp_secret"):
            raise HTTPException(409, "MFA is already enabled.")
        secret = pyotp.random_base32()
        owner["pending_totp"] = secret
        store.put("owner", "owner", owner)
        return {"secret": secret, "uri": pyotp.TOTP(secret).provisioning_uri("Owner", issuer_name="Jozi Buddy")}

    @app.post("/api/v1/auth/mfa/confirm", response_model=out.RecoveryCodes)
    def mfa_confirm(body: CodeInput, request: Request):
        auth.mutation(request)
        auth.throttle(request)
        owner = store.get("owner", "owner")
        secret = owner.get("pending_totp")
        if not secret or not pyotp.TOTP(secret).verify(body.code, valid_window=1):
            raise HTTPException(400, "The authenticator code did not match.")
        codes = [secrets.token_hex(16) for _ in range(8)]
        owner["totp_secret"] = owner.pop("pending_totp")
        owner["recovery_codes"] = [digest(code) for code in codes]
        store.put("owner", "owner", owner)
        auth.revoke_others(request)
        store.audit("mfa_enabled")
        return {"recovery_codes": ["-".join(code[index:index+8] for index in range(0, 32, 8)) for code in codes]}

    @app.post("/api/v1/auth/mfa/disable", response_model=out.Operation)
    def mfa_disable(body: MFAOff, request: Request):
        auth.mutation(request)
        auth.throttle(request)
        owner = store.get("owner", "owner")
        if not auth.password(body.password.get_secret_value()) or not auth.verify_code(body.code, owner):
            raise HTTPException(401, "Those verification details did not match.")
        for key in ("totp_secret", "recovery_codes", "last_totp_step"):
            owner.pop(key, None)
        store.put("owner", "owner", owner)
        auth.revoke_others(request)
        store.audit("mfa_disabled")
        return {"ok": True}

    @app.get("/api/v1/profile", response_model=out.Profile)
    def profile(request: Request):
        auth.session(request)
        return store.get("profile", "owner") or {"name": None}

    @app.patch("/api/v1/profile", response_model=out.Profile)
    def update_profile(body: ProfileInput, request: Request):
        auth.mutation(request)
        try:
            name = validate_name(body.name) if body.name else None
        except ValueError as error:
            raise HTTPException(422, str(error)) from None
        store.put("profile", "owner", {"name": name})
        store.audit("preferred_name_updated")
        return {"name": name}

    @app.get("/api/v1/documents", response_model=list[out.Document])
    def documents(request: Request):
        auth.session(request)
        return [summary(value) for value in store.list("document")]

    @app.post("/api/v1/documents", status_code=202, response_model=out.Document)
    async def upload(request: Request, background: BackgroundTasks):
        auth.mutation(request)
        if request.headers.get("content-type", "").split(";")[0] != "application/pdf":
            store.audit("pdf_upload", "blocked", "invalid_type")
            raise HTTPException(415, "Choose a PDF file.")
        filename = unquote(request.headers.get("x-file-name", "document.pdf"))
        if len(filename) > 180 or not filename.lower().endswith(".pdf") or any(char in filename for char in ("/", "\\", "\x00", "..")) or any(ord(char) < 32 for char in filename):
            store.audit("pdf_upload", "blocked", "invalid_filename")
            raise HTTPException(400, "Use a simple PDF filename without folder paths.")
        if not store.consume(f"upload:{int(time.time() // 60)}", 5):
            raise HTTPException(429, "Please wait before uploading another document.")
        data = bytearray()
        async for piece in request.stream():
            data.extend(piece)
            if len(data) > 10 * 1024 * 1024:
                store.audit("pdf_upload", "blocked", "size_limit")
                raise HTTPException(413, "PDFs must be smaller than 10 MiB.")
        file_hash = hashlib.sha256(data).hexdigest()
        for existing in store.list("document"):
            if existing["hash"] == file_hash and existing.get("redaction_version") == 1:
                return summary(existing) | {"cached": True}
        try:
            value = await asyncio.to_thread(prepare_document, bytes(data), filename)
        except ValueError as error:
            store.audit("pdf_upload", "blocked", "structural_validation")
            raise HTTPException(400, str(error)) from None
        store.put_bytes("pdf", value["id"], bytes(data), parent=value["id"])
        store.put("document", value["id"], value)
        store.audit("pdf_uploaded", document_id=value["id"])
        background.add_task(ai.index, value["id"])
        return summary(value)

    @app.get("/api/v1/documents/{identifier}", response_model=out.DocumentDetail)
    def document_detail(identifier: str, request: Request):
        auth.session(request)
        value = document(identifier)
        return summary(value) | {"pages": value["pages"]}

    @app.get("/api/v1/documents/{identifier}/file")
    def document_file(identifier: str, request: Request):
        auth.session(request)
        document(identifier)
        content = store.get_bytes("pdf", identifier)
        if content is None:
            raise HTTPException(404, "This PDF is not available.")
        return Response(content, media_type="application/pdf", headers={"Content-Disposition": 'inline; filename="document.pdf"'})

    @app.post("/api/v1/documents/{identifier}/index", response_model=out.Operation)
    def reindex(identifier: str, request: Request, background: BackgroundTasks):
        auth.mutation(request)
        value = document(identifier)
        if value["status"] == "indexing":
            raise HTTPException(409, "This document is already being indexed.")
        value["status"] = "indexing"
        store.put("document", identifier, value)
        background.add_task(ai.index, identifier)
        return {"ok": True}

    @app.delete("/api/v1/documents/{identifier}", response_model=out.Operation)
    def delete_document(identifier: str, request: Request):
        auth.mutation(request)
        document(identifier)
        store.delete_document(identifier)
        store.audit("document_deleted", document_id=identifier)
        return {"ok": True}

    @app.post("/api/v1/documents/{identifier}/narration", response_model=out.Narration)
    def narration(identifier: str, body: NarrateInput, request: Request):
        auth.mutation(request)
        value = document(identifier)
        if body.page > len(value["pages"]):
            raise HTTPException(404, "That page is not available.")
        page = value["pages"][body.page - 1]
        if page["scanned"]:
            raise HTTPException(409, "This page needs OCR before it can be read aloud.")
        text = page["text"]
        if body.selection:
            selection = " ".join(redact(body.selection)[0].split())
            if selection not in " ".join(text.split()):
                raise HTTPException(422, "Select text from this page, or use Read page.")
            text = selection
        return {"text": redact(text)[0], "page": body.page}

    @app.post("/api/v1/ask", response_model=out.Answer)
    def ask(body: AskInput, request: Request):
        auth.mutation(request)
        if not store.consume(f"ask:{int(time.time() // 60)}", 15):
            raise HTTPException(429, "Please give Jozi a moment before another question.")
        return ai.ask(document(body.document_id), body.question, body.page)

    @app.get("/api/v1/quizzes", response_model=list[out.QuizSummary])
    def quizzes(request: Request):
        auth.session(request)
        return [{key: value[key] for key in ("id", "document_id", "title", "created")} | {"count": len(value["questions"]), "needs_review": any(question["needs_review"] for question in value["questions"])} for value in store.list("quiz")]

    @app.post("/api/v1/quizzes/generate", response_model=out.Quiz)
    def generate(body: GenerateInput, request: Request):
        auth.mutation(request)
        source = document(body.document_id)
        value = ai.generate(source, body)
        value.update(id=str(uuid4()), document_id=source["id"], created=time.time())
        save_child("quiz", value["id"], value, source["id"])
        store.audit("quiz_generated", document_id=source["id"])
        return value

    @app.get("/api/v1/quizzes/{identifier}", response_model=out.Quiz)
    def quiz_detail(identifier: str, request: Request):
        auth.session(request)
        return quiz(identifier)

    @app.put("/api/v1/quizzes/{identifier}", response_model=out.Quiz)
    def edit_quiz(identifier: str, body: QuizDraft, request: Request):
        auth.mutation(request)
        value = quiz(identifier)
        source = document(value["document_id"])
        allowed = {page["page"] for page in source["pages"] if not page["scanned"]}
        if len({question.id for question in body.questions}) != len(body.questions):
            raise HTTPException(422, "Question identifiers must be unique.")
        old = {question["id"]: question for question in value["questions"]}
        edited = body.model_dump()
        for question in edited["questions"]:
            if not set(question["pages"]) <= allowed:
                raise HTTPException(422, "Choose valid readable source pages.")
            previous = old.get(question["id"], {})
            if {key: item for key, item in question.items() if key != "needs_review"} != {key: item for key, item in previous.items() if key != "needs_review"}:
                question["needs_review"] = True
        edited = redact_data(edited)
        value.update(QuizDraft.model_validate(edited).model_dump())
        save_child("quiz", identifier, value, value["document_id"])
        store.audit("quiz_edited", document_id=value["document_id"])
        return value

    @app.get("/api/v1/quizzes/{identifier}/export/{kind}")
    def export(identifier: str, kind: str, request: Request):
        auth.session(request)
        if kind not in {"questions", "answers"}:
            raise HTTPException(404)
        value = quiz(identifier)
        content = export_quiz(value, answers=kind == "answers")
        store.audit("quiz_exported", document_id=value["document_id"])
        return Response(content, media_type="application/pdf", headers={"Content-Disposition": f'attachment; filename="jozi-{kind}.pdf"'})

    @app.post("/api/v1/quizzes/{identifier}/attempts", response_model=out.Attempt)
    def start_attempt(identifier: str, body: StartAttempt, request: Request):
        auth.mutation(request)
        value = quiz(identifier)
        record = {"id": str(uuid4()), "quiz_id": identifier, "document_id": value["document_id"], "title": value["title"],
            "mode": body.mode, "questions": value["questions"], "answers": {}, "grades": {}, "submitted": False, "created": time.time()}
        save_child("attempt", record["id"], record, record["document_id"])
        return public_attempt(record)

    @app.get("/api/v1/attempts", response_model=list[out.Attempt])
    def attempts(request: Request):
        auth.session(request)
        return [public_attempt(value) for value in store.list("attempt")]

    @app.get("/api/v1/attempts/{identifier}", response_model=out.Attempt)
    def get_attempt(identifier: str, request: Request):
        auth.session(request)
        return public_attempt(attempt(identifier))

    @app.post("/api/v1/attempts/{identifier}/answer", response_model=out.Attempt)
    def answer_question(identifier: str, body: SubmitAnswer, request: Request):
        auth.mutation(request)
        value = attempt(identifier)
        if value["submitted"]:
            raise HTTPException(409, "This self-test has already been submitted.")
        question = next((question for question in value["questions"] if question["id"] == body.question_id), None)
        if question is None:
            raise HTTPException(404, "That question is not part of this attempt.")
        if question["type"] == "mcq" and body.answer not in {"0", "1", "2", "3"}:
            raise HTTPException(422, "Choose one answer.")
        safe = redact(body.answer)[0]
        if not safe.strip():
            raise HTTPException(422, "Write an answer before saving.")
        value["answers"][body.question_id] = safe
        if value["mode"] == "practice":
            value["grades"][body.question_id] = ai.mark(question, safe, document(value["document_id"])) | {"pages": question["pages"], "correct_answer": question["options"][question["correct_index"]] if question["type"] == "mcq" else question["model_answer"]}
        save_child("attempt", identifier, value, value["document_id"])
        return public_attempt(value)

    @app.post("/api/v1/attempts/{identifier}/submit", response_model=out.Attempt)
    def submit_attempt(identifier: str, request: Request):
        auth.mutation(request)
        value = attempt(identifier)
        if not value["submitted"]:
            source = document(value["document_id"])
            for question in value["questions"]:
                if question["id"] not in value["grades"]:
                    answer = value["answers"].get(question["id"], "")
                    grade = ai.mark(question, answer, source) if answer else {"score": 0, "feedback": "No answer was submitted."}
                    value["grades"][question["id"]] = grade | {"pages": question["pages"], "correct_answer": question["options"][question["correct_index"]] if question["type"] == "mcq" else question["model_answer"]}
                    save_child("attempt", identifier, value, value["document_id"])
            value["submitted"] = True
            save_child("attempt", identifier, value, value["document_id"])
            store.audit("attempt_submitted", document_id=value["document_id"])
        return public_attempt(value)

    @app.get("/api/v1/security", response_model=out.Security)
    def security(request: Request):
        auth.session(request)
        owner = store.get("owner", "owner")
        return {"mfa_enabled": bool(owner.get("totp_secret")), "limits": ai.limits(),
            "usage": {category: store.used(f"{category}:{day()}") for category in DEFAULT_LIMITS},
            "tokens": {"input": store.used(f"tokens_in:{day()}"), "output": store.used(f"tokens_out:{day()}")},
            "controls": {"encrypted_storage": True, "dpapi_key": store.dpapi_protected, "csrf": True, "origin_checks": True,
                "isolated_parser": True, "redaction": True, "credential_location": "Backend AWS credential chain", "bind": "127.0.0.1"},
            "events": store.list("audit", limit=60), "data_location": str(store.directory)}

    @app.patch("/api/v1/settings/limits", response_model=LimitsInput)
    def limits(body: LimitsInput, request: Request):
        auth.mutation(request)
        store.put("settings", "limits", body.model_dump())
        store.audit("daily_allowances_updated")
        return body.model_dump()

    @app.get("/api/v1/security/evidence/{kind}")
    def evidence(kind: str, request: Request):
        auth.session(request)
        filenames = {"threat-model": "SECURITY.md", "verification": "VERIFICATION.md", "demo": "DEMO.md"}
        filename = filenames.get(kind)
        if filename is None or not (ROOT / "docs" / filename).is_file():
            raise HTTPException(404, "That evidence file is not available.")
        return FileResponse(ROOT / "docs" / filename, media_type="text/plain", filename=filename)

    @app.get("/api/v1/ai/status", response_model=out.AWSStatus)
    def ai_status(request: Request):
        auth.session(request)
        try:
            from .aws import aws_session
            from botocore.config import Config
            session = aws_session()
            identity = session.client("sts", config=Config(connect_timeout=5, read_timeout=5, retries={"max_attempts": 0})).get_caller_identity()
            return {"authenticated": bool(identity.get("Arn")), "region": "us-east-1", "models": ["Nova 2 Lite (US)", "Titan Text Embeddings V2", "Nova 2.5 Sonic"]}
        except Exception as error:
            from .aws import aws_problem
            return {"authenticated": False, "message": aws_problem(error)}

    @app.websocket("/api/v1/voice")
    async def voice(websocket: WebSocket):
        from .voice import conversation
        await conversation(websocket, store, auth, ai, app.state.voice_lock)

    # Static assets are public; every data operation above is authenticated.
    build = ROOT / "web" / "dist"
    if (build / "assets").is_dir():
        app.mount("/assets", StaticFiles(directory=build / "assets"), name="assets")

    @app.get("/{path:path}")
    def frontend(path: str):
        if path.startswith("api/"):
            raise HTTPException(404)
        if not (build / "index.html").exists():
            return JSONResponse({"detail": "Build the frontend with npm run build in the web folder, then restart the app."}, status_code=503)
        return FileResponse(build / "index.html")

    return app
