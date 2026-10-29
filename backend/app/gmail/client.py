"""Google OAuth + the few Gmail API calls the tracker needs (read-only)."""

import base64
import html
import re
import time
from dataclasses import dataclass
from urllib.parse import urlencode

import httpx
import jwt
from cryptography.fernet import Fernet

from ..config import settings

AUTH_URL = "https://accounts.google.com/o/oauth2/v2/auth"
TOKEN_URL = "https://oauth2.googleapis.com/token"
REVOKE_URL = "https://oauth2.googleapis.com/revoke"
GMAIL = "https://gmail.googleapis.com/gmail/v1/users/me"
SCOPES = "openid email https://www.googleapis.com/auth/gmail.readonly"


class GmailAuthError(Exception):
    """The refresh token was revoked or expired; the user must reconnect."""


class HistoryExpired(Exception):
    """The stored historyId is too old; fall back to a date search."""


# ---- Token storage ------------------------------------------------------------
def _fernet() -> Fernet:
    if not settings.token_encryption_key:
        raise RuntimeError("TOKEN_ENCRYPTION_KEY is not set")
    return Fernet(settings.token_encryption_key.encode())


def encrypt(token: str) -> str:
    return _fernet().encrypt(token.encode()).decode()


def decrypt(token: str) -> str:
    return _fernet().decrypt(token.encode()).decode()


# ---- OAuth -------------------------------------------------------------------
def _state_key() -> str:
    # Signs the OAuth "state" so the callback knows which user started the flow.
    return settings.token_encryption_key or settings.google_client_secret


def consent_url(user_id: str, email: str | None) -> str:
    state = jwt.encode({"sub": user_id, "purpose": "gmail", "exp": int(time.time()) + 600},
                       _state_key(), algorithm="HS256")
    params = {
        "client_id": settings.google_client_id,
        "redirect_uri": settings.gmail_redirect_uri,
        "response_type": "code",
        "scope": SCOPES,
        "access_type": "offline",   # we need a refresh token for background syncs
        "prompt": "consent",        # Google only re-issues a refresh token with this
        "include_granted_scopes": "true",
        "state": state,
    }
    if email:
        params["login_hint"] = email
    return f"{AUTH_URL}?{urlencode(params)}"


def user_id_from_state(state: str) -> str:
    claims = jwt.decode(state, _state_key(), algorithms=["HS256"])
    if claims.get("purpose") != "gmail":
        raise jwt.InvalidTokenError("wrong purpose")
    return claims["sub"]


@dataclass
class Tokens:
    refresh_token: str
    access_token: str
    email: str


def exchange_code(code: str) -> Tokens:
    r = httpx.post(TOKEN_URL, data={
        "code": code,
        "client_id": settings.google_client_id,
        "client_secret": settings.google_client_secret,
        "redirect_uri": settings.gmail_redirect_uri,
        "grant_type": "authorization_code",
    }, timeout=20)
    r.raise_for_status()
    body = r.json()
    if "refresh_token" not in body:
        raise GmailAuthError("Google did not return a refresh token")
    # The id_token came straight from Google over TLS, so its claims can be read without re-verifying.
    email = jwt.decode(body["id_token"], options={"verify_signature": False}).get("email", "")
    return Tokens(body["refresh_token"], body["access_token"], email)


def refresh_access_token(refresh_token: str) -> str:
    r = httpx.post(TOKEN_URL, data={
        "client_id": settings.google_client_id,
        "client_secret": settings.google_client_secret,
        "refresh_token": refresh_token,
        "grant_type": "refresh_token",
    }, timeout=20)
    if r.status_code in (400, 401):  # invalid_grant: revoked, password changed, or 7-day testing expiry
        raise GmailAuthError(r.json().get("error_description", "Gmail access was revoked"))
    r.raise_for_status()
    return r.json()["access_token"]


def revoke(refresh_token: str) -> None:
    try:
        httpx.post(REVOKE_URL, data={"token": refresh_token}, timeout=10)
    except httpx.HTTPError:
        pass  # best effort; the user can also remove access at myaccount.google.com


# ---- Gmail API ---------------------------------------------------------------
@dataclass
class Message:
    id: str
    thread_id: str
    internal_date_ms: int
    sender: str
    subject: str
    labels: list[str]
    body: str = ""


class Gmail:
    def __init__(self, access_token: str) -> None:
        self._c = httpx.Client(base_url=GMAIL, timeout=30,
                               headers={"Authorization": f"Bearer {access_token}"})

    def _get(self, path: str, params: dict | None = None) -> dict:
        for attempt in range(3):
            r = self._c.get(path, params=params)
            if r.status_code == 429 or r.status_code >= 500:
                time.sleep(2 ** attempt)  # rate limited: back off and retry
                continue
            if r.status_code == 401:
                raise GmailAuthError("Access token rejected")
            if r.status_code == 404 and path == "/history":
                raise HistoryExpired()
            r.raise_for_status()
            return r.json()
        r.raise_for_status()
        return {}

    def current_history_id(self) -> str:
        return str(self._get("/profile")["historyId"])

    def search(self, query: str, limit: int) -> list[str]:
        ids: list[str] = []
        token = None
        while len(ids) < limit:
            params = {"q": query, "maxResults": min(100, limit - len(ids))}
            if token:
                params["pageToken"] = token
            page = self._get("/messages", params)
            ids += [m["id"] for m in page.get("messages", [])]
            token = page.get("nextPageToken")
            if not token:
                break
        return ids

    def added_since(self, history_id: str, limit: int) -> list[str]:
        """IDs of messages that arrived in the inbox after history_id."""
        ids: list[str] = []
        token = None
        while len(ids) < limit:
            params = {"startHistoryId": history_id, "historyTypes": "messageAdded",
                      "labelId": "INBOX", "maxResults": 500}
            if token:
                params["pageToken"] = token
            page = self._get("/history", params)
            for h in page.get("history", []):
                ids += [m["message"]["id"] for m in h.get("messagesAdded", [])]
            token = page.get("nextPageToken")
            if not token:
                break
        return list(dict.fromkeys(ids))[:limit]  # dedupe, keep order

    def metadata(self, message_id: str) -> Message:
        m = self._get(f"/messages/{message_id}",
                      {"format": "metadata", "metadataHeaders": ["From", "Subject"]})
        headers = {h["name"].lower(): h["value"] for h in m.get("payload", {}).get("headers", [])}
        return Message(id=m["id"], thread_id=m.get("threadId", ""),
                       internal_date_ms=int(m.get("internalDate", 0)),
                       sender=headers.get("from", ""), subject=headers.get("subject", ""),
                       labels=m.get("labelIds", []))

    def body_text(self, message_id: str) -> str:
        m = self._get(f"/messages/{message_id}", {"format": "full"})
        plain, rich = _collect_parts(m.get("payload", {}))
        text = plain or _html_to_text(rich)
        return re.sub(r"\s+", " ", text).strip()


def _decode(data: str) -> str:
    return base64.urlsafe_b64decode(data + "=" * (-len(data) % 4)).decode("utf-8", "replace")


def _collect_parts(part: dict) -> tuple[str, str]:
    plain, rich = "", ""
    mime = part.get("mimeType", "")
    data = part.get("body", {}).get("data")
    if data and mime == "text/plain":
        plain += _decode(data)
    elif data and mime == "text/html":
        rich += _decode(data)
    for child in part.get("parts", []) or []:
        p, h = _collect_parts(child)
        plain, rich = plain + p, rich + h
    return plain, rich


def _html_to_text(raw: str) -> str:
    raw = re.sub(r"(?is)<(script|style).*?</\1>", " ", raw)
    return html.unescape(re.sub(r"<[^>]+>", " ", raw))
