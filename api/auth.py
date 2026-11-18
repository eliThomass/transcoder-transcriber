# Login with Cognito managed login (OAuth code flow + PKCE), then our own session cookie.
# Passwords never reach this API, and Cognito's tokens are checked once at login and then discarded.
import base64
import hashlib
import hmac
import secrets
import sqlite3
from datetime import timedelta
from typing import Annotated
from urllib.parse import urlencode

import httpx
import jwt
from fastapi import APIRouter, Cookie, Depends, HTTPException, Response
from fastapi.responses import RedirectResponse

from api import db
from api.config import (API_PUBLIC_URL, COGNITO_CLIENT_ID, COGNITO_CLIENT_SECRET, COGNITO_DOMAIN,
                        COGNITO_ISSUER, COOKIE_SECURE, FRONTEND_URL, SESSION_HOURS)
from api.schemas import LogoutResponse, User

router = APIRouter(prefix="/auth", tags=["auth"])
Db = Annotated[sqlite3.Connection, Depends(db.get_db)]

CALLBACK_URL = f"{API_PUBLIC_URL}/auth/callback"  # must exactly match the app client's callback URL
SESSION_COOKIE = "session"
FLOW_COOKIE = "login_flow"  # holds state, nonce and the PKCE verifier between /login and /callback
LOGIN_FAILED = "Login failed or expired. Try again."
_jwks = jwt.PyJWKClient(f"{COGNITO_ISSUER}/.well-known/jwks.json")  # Cognito's public signing keys, cached


# Session IDs are stored hashed, so a leaked database can't be used to log in.
def _hash(session_id: str) -> str:
    return hashlib.sha256(session_id.encode()).hexdigest()


# Sets an httpOnly cookie. Lax (not Strict) so it's sent on the redirect back from Cognito.
def _set_cookie(resp: Response, name: str, value: str, max_age: int, path: str = "/") -> None:
    resp.set_cookie(name, value, max_age=max_age, path=path, httponly=True, secure=COOKIE_SECURE, samesite="lax")


# Deletes a cookie set by _set_cookie (same name, path and flags).
def _clear_cookie(resp: Response, name: str, path: str = "/") -> None:
    resp.delete_cookie(name, path=path, httponly=True, secure=COOKIE_SECURE, samesite="lax")


# Constant-time string compare, so timing doesn't leak how much of a secret matched.
def _same(a: str, b: str) -> bool:
    return bool(a and b) and hmac.compare_digest(a.encode(), b.encode())


# Redirects to a managed login page with fresh state (anti-CSRF), nonce (anti-replay) and PKCE challenge.
def _start_flow(page: str) -> RedirectResponse:
    if not (COGNITO_DOMAIN and COGNITO_CLIENT_ID and COGNITO_CLIENT_SECRET):
        raise HTTPException(503, "Login isn't configured. See docs/aws-resources.md.")
    state, nonce, verifier = secrets.token_urlsafe(32), secrets.token_urlsafe(32), secrets.token_urlsafe(32)
    challenge = base64.urlsafe_b64encode(hashlib.sha256(verifier.encode()).digest()).rstrip(b"=").decode()
    query = urlencode({
        "response_type": "code", "client_id": COGNITO_CLIENT_ID, "redirect_uri": CALLBACK_URL,
        "scope": "openid email", "state": state, "nonce": nonce,
        "code_challenge": challenge, "code_challenge_method": "S256",
    })
    resp = RedirectResponse(f"{COGNITO_DOMAIN}/{page}?{query}", status_code=303)
    _set_cookie(resp, FLOW_COOKIE, f"{state}.{nonce}.{verifier}", max_age=600, path="/auth")  # 10 minutes to log in
    return resp


# Checks the ID token's signature against Cognito's keys, plus issuer, audience, expiry, type and nonce.
def _verify_id_token(id_token: str, nonce: str) -> dict:
    try:
        key = _jwks.get_signing_key_from_jwt(id_token).key
        claims = jwt.decode(id_token, key, algorithms=["RS256"], audience=COGNITO_CLIENT_ID,
                            issuer=COGNITO_ISSUER, options={"require": ["exp", "iat", "sub"]})
    except jwt.PyJWTError:
        raise HTTPException(400, LOGIN_FAILED)
    if claims.get("token_use") != "id" or not _same(claims.get("nonce", ""), nonce) or not claims.get("email_verified"):
        raise HTTPException(400, LOGIN_FAILED)
    return claims


# Sends the browser to Cognito's sign-in page.
@router.get("/login")
def login() -> RedirectResponse:
    return _start_flow("oauth2/authorize")


# Sends the browser to Cognito's sign-up page (same flow, so the user ends up logged in).
@router.get("/signup")
def signup() -> RedirectResponse:
    return _start_flow("signup")


# Cognito redirects here after login: check state, trade the code for tokens, verify them, start a session.
@router.get("/callback")
def callback(conn: Db, code: str = "", state: str = "",
             login_flow: Annotated[str, Cookie()] = "") -> RedirectResponse:
    flow_state, nonce, verifier = (login_flow.split(".") + ["", "", ""])[:3]
    if not code or not _same(state, flow_state):
        raise HTTPException(400, LOGIN_FAILED)
    # Server-to-server: the client secret and PKCE verifier prove this API started the login.
    tokens = httpx.post(
        f"{COGNITO_DOMAIN}/oauth2/token", auth=(COGNITO_CLIENT_ID, COGNITO_CLIENT_SECRET), timeout=10,
        data={"grant_type": "authorization_code", "code": code, "redirect_uri": CALLBACK_URL, "code_verifier": verifier},
    )
    if tokens.status_code != 200:
        raise HTTPException(400, LOGIN_FAILED)
    claims = _verify_id_token(tokens.json().get("id_token", ""), nonce)

    now, session_id = db.utcnow(), secrets.token_urlsafe(32)  # a new random ID every login (no session fixation)
    with conn:
        conn.execute("DELETE FROM sessions WHERE expires_at <= ?", (db.to_db(now),))  # tidy up expired sessions
        conn.execute("INSERT INTO users (id, email, created_at) VALUES (?, ?, ?) "
                     "ON CONFLICT(id) DO UPDATE SET email = excluded.email",
                     (claims["sub"], claims["email"], db.to_db(now)))
        conn.execute("INSERT INTO sessions (id_hash, user_id, expires_at) VALUES (?, ?, ?)",
                     (_hash(session_id), claims["sub"], db.to_db(now + timedelta(hours=SESSION_HOURS))))
    resp = RedirectResponse(f"{FRONTEND_URL}/#/library", status_code=303)
    _set_cookie(resp, SESSION_COOKIE, session_id, max_age=SESSION_HOURS * 3600)
    _clear_cookie(resp, FLOW_COOKIE, path="/auth")  # single use
    return resp


# FastAPI dependency: the logged-in user from the session cookie, or 401.
def current_user(conn: Db, session: Annotated[str, Cookie()] = "") -> sqlite3.Row:
    row = conn.execute(
        "SELECT users.* FROM sessions JOIN users ON users.id = sessions.user_id "
        "WHERE sessions.id_hash = ? AND sessions.expires_at > ?",
        (_hash(session), db.to_db(db.utcnow())),
    ).fetchone()
    if not row:
        raise HTTPException(401, "Log in to continue.")
    return row


CurrentUser = Annotated[sqlite3.Row, Depends(current_user)]


# Returns the logged-in user (the frontend calls this on page load).
@router.get("/me")
def me(user: CurrentUser) -> User:
    return User(id=user["id"], email=user["email"], created_at=user["created_at"])


# Ends our session; the frontend then opens the returned URL to end the Cognito login too.
@router.post("/logout")
def logout(response: Response, conn: Db, session: Annotated[str, Cookie()] = "") -> LogoutResponse:
    with conn:
        conn.execute("DELETE FROM sessions WHERE id_hash = ?", (_hash(session),))
    _clear_cookie(response, SESSION_COOKIE)
    return LogoutResponse(url=f"{COGNITO_DOMAIN}/logout?"
                              + urlencode({"client_id": COGNITO_CLIENT_ID, "logout_uri": f"{FRONTEND_URL}/"}))
