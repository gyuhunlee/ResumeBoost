"""Small server-side Supabase client (PostgREST, Auth admin, Storage) over httpx.

Uses the service key, which bypasses row-level security, so every query here
MUST filter by the signed-in user's id. Keeping it this thin avoids pulling in
the full supabase-py SDK for a handful of calls.
"""

from typing import Any

import httpx

from .config import settings


class DB:
    def __init__(self) -> None:
        key = settings.supabase_service_key
        if not key:
            raise RuntimeError("SUPABASE_SERVICE_KEY is not set in backend/.env")
        headers = {"apikey": key}
        # Legacy service_role keys are JWTs and also go in Authorization;
        # the newer sb_secret_... keys only go in the apikey header.
        if key.startswith("eyJ"):
            headers["Authorization"] = f"Bearer {key}"
        self._client = httpx.Client(base_url=settings.supabase_url, headers=headers, timeout=20)

    # ---- PostgREST ---------------------------------------------------------
    def select(self, table: str, params: dict[str, str]) -> list[dict[str, Any]]:
        r = self._client.get(f"/rest/v1/{table}", params=params)
        r.raise_for_status()
        return r.json()

    def select_one(self, table: str, params: dict[str, str]) -> dict[str, Any] | None:
        rows = self.select(table, {**params, "limit": "1"})
        return rows[0] if rows else None

    def insert(self, table: str, row: dict[str, Any], *, on_conflict: str | None = None,
               ignore_duplicates: bool = False, upsert: bool = False) -> list[dict[str, Any]]:
        prefer = ["return=representation"]
        if ignore_duplicates:
            prefer.append("resolution=ignore-duplicates")
        elif upsert:
            prefer.append("resolution=merge-duplicates")
        params = {"on_conflict": on_conflict} if on_conflict else {}
        r = self._client.post(f"/rest/v1/{table}", params=params, json=row,
                              headers={"Prefer": ",".join(prefer)})
        r.raise_for_status()
        return r.json()

    def update(self, table: str, params: dict[str, str], changes: dict[str, Any]) -> list[dict[str, Any]]:
        r = self._client.patch(f"/rest/v1/{table}", params=params, json=changes,
                               headers={"Prefer": "return=representation"})
        r.raise_for_status()
        return r.json()

    def delete(self, table: str, params: dict[str, str]) -> None:
        self._client.delete(f"/rest/v1/{table}", params=params).raise_for_status()

    # ---- Storage -----------------------------------------------------------
    def remove_user_files(self, bucket: str, user_id: str) -> None:
        """Delete every object under <bucket>/<user_id>/."""
        for _ in range(100):  # 100 files per page; the guard stops a runaway loop
            r = self._client.post(f"/storage/v1/object/list/{bucket}",
                                  json={"prefix": user_id, "limit": 100, "offset": 0})
            r.raise_for_status()
            names = [f"{user_id}/{o['name']}" for o in r.json() if o.get("id")]
            if not names:
                return
            self._client.request("DELETE", f"/storage/v1/object/{bucket}",
                                 json={"prefixes": names}).raise_for_status()
        raise RuntimeError("Too many files to delete in one request")

    # ---- Auth admin --------------------------------------------------------
    def delete_auth_user(self, user_id: str) -> None:
        """Deletes the login. ON DELETE CASCADE removes the user's table rows."""
        self._client.delete(f"/auth/v1/admin/users/{user_id}").raise_for_status()


db = DB()


def eq(value: str) -> str:
    return f"eq.{value}"
