import hmac
import secrets
import time
import pyotp
from argon2 import PasswordHasher
from argon2.exceptions import VerificationError, InvalidHashError
from fastapi import HTTPException, Request, Response
from .storage import Store, digest

COOKIE = "jb_session"
hasher = PasswordHasher()


class Auth:
    def __init__(self, store: Store):
        self.store = store

    def issue(self, response: Response, kind="owner"):
        token, csrf = secrets.token_urlsafe(32), secrets.token_urlsafe(32)
        now = time.time()
        self.store.put("session", digest(token), {"kind": kind, "csrf": csrf, "created": now, "last": now})
        response.set_cookie(COOKIE, token, httponly=True, samesite="strict", secure=False, max_age=43200, path="/")
        return {"authenticated": kind == "owner", "csrf": csrf, "mfa_required": kind == "pending"}

    def session(self, request: Request, kinds=("owner",)):
        token = request.cookies.get(COOKIE, "")
        identifier = digest(token)
        session = self.store.get("session", identifier) if token else None
        if not session or session["kind"] not in kinds:
            raise HTTPException(401, "Please sign in to continue.")
        now = time.time()
        lifetime = 300 if session["kind"] != "owner" else 43200
        if now - session["last"] > 1800 or now - session["created"] > lifetime:
            self.store.delete("session", identifier)
            raise HTTPException(401, "Your session expired. Please sign in again.")
        if now - session["last"] > 30:
            session["last"] = now
            self.store.put("session", identifier, session)
        return session

    def mutation(self, request: Request, kinds=("owner",)):
        session = self.session(request, kinds)
        if not hmac.compare_digest(request.headers.get("x-csrf-token", "").encode(), session["csrf"].encode()):
            self.store.audit("csrf_check", "blocked", "invalid_token")
            raise HTTPException(403, "Refresh this page and try again.")
        return session

    def revoke(self, request: Request):
        self.store.delete("session", digest(request.cookies.get(COOKIE, "")))

    def revoke_others(self, request: Request):
        keep = digest(request.cookies.get(COOKIE, ""))
        with self.store.connect() as connection:
            connection.execute("DELETE FROM records WHERE kind='session' AND id<>?", (keep,))

    def throttle(self, request: Request):
        peer = request.client.host if request.client else "local"
        bucket = f"login:{digest(peer)}:{int(time.time() // 60)}"
        if not self.store.consume(bucket, 5):
            self.store.audit("login", "blocked", "rate_limit")
            raise HTTPException(429, "Too many attempts. Please wait one minute.")

    def password(self, password: str) -> bool:
        owner = self.store.get("owner", "owner")
        try:
            return bool(owner and hasher.verify(owner["password"], password))
        except (VerificationError, InvalidHashError):
            return False

    def verify_code(self, code: str, owner: dict) -> bool:
        recovery_used = False
        def verify(current):
            nonlocal recovery_used
            if current is None:
                return None, False
            result = self._match_code(code, current)
            recovery_used = current.pop("_recovery_used", False)
            if result:
                owner.clear()
                owner.update(current)
            return current, result
        result = self.store.mutate("owner", "owner", verify)
        if result and recovery_used:
            self.store.audit("recovery_code", "allowed", "single_use")
        return result

    def _match_code(self, code, owner):
        secret = owner.get("totp_secret")
        if secret:
            totp = pyotp.TOTP(secret)
            step = int(time.time() // 30)
            for candidate in (step - 1, step, step + 1):
                if candidate > owner.get("last_totp_step", -1) and hmac.compare_digest(totp.at(candidate * 30), code.strip()):
                    owner["last_totp_step"] = candidate
                    return True
        recovery_hash = digest(code.replace("-", "").replace(" ", "").lower())
        codes = owner.get("recovery_codes", [])
        if recovery_hash in codes:
            codes.remove(recovery_hash)
            owner["_recovery_used"] = True
            return True
        return False
