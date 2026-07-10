"""
All database access goes through PostgREST directly via httpx —
NOT the supabase-py SDK, per spec.

IMPORTANT PRIVACY RULE:
Every function that reads/writes a table MUST take a user_id and
include it as a filter. The service role key bypasses Row Level
Security, so this module is the only thing standing between one
user's data and another's. Never call these without a user_id filter
on user-owned tables.
"""
import httpx
from fastapi import HTTPException
from .config import settings

# ---------------------------------------------------------------------
# Low-level PostgREST request (uses SERVICE ROLE key — full DB access)
# ---------------------------------------------------------------------

def _service_headers(extra: dict | None = None) -> dict:
    headers = {
        "apikey": settings.SUPABASE_SERVICE_KEY,
        "Authorization": f"Bearer {settings.SUPABASE_SERVICE_KEY}",
        "Content-Type": "application/json",
    }
    if extra:
        headers.update(extra)
    return headers


async def db_select(table: str, params: dict) -> list[dict]:
    """
    params example: {"user_id": "eq.<uuid>", "select": "*", "order": "created_at.desc"}
    Every call site MUST include a user_id filter in params.
    """
    if not any(k == "user_id" for k in params):
        raise RuntimeError(f"db_select on '{table}' called without a user_id filter — refusing.")
    async with httpx.AsyncClient() as client:
        resp = await client.get(
            f"{settings.SUPABASE_REST_URL}/{table}",
            headers=_service_headers(),
            params=params,
            timeout=30.0,
        )
    if resp.status_code >= 400:
        raise HTTPException(status_code=500, detail=f"DB select error on {table}: {resp.text}")
    return resp.json()


async def db_insert(table: str, row: dict | list[dict]) -> list[dict]:
    """
    row (or every row in the list) MUST contain a user_id field.
    """
    rows = row if isinstance(row, list) else [row]
    for r in rows:
        if "user_id" not in r:
            raise RuntimeError(f"db_insert on '{table}' called without user_id in row — refusing.")
    async with httpx.AsyncClient() as client:
        resp = await client.post(
            f"{settings.SUPABASE_REST_URL}/{table}",
            headers=_service_headers({"Prefer": "return=representation"}),
            json=row,
            timeout=30.0,
        )
    if resp.status_code >= 400:
        raise HTTPException(status_code=500, detail=f"DB insert error on {table}: {resp.text}")
    return resp.json()


async def db_update(table: str, params: dict, patch: dict) -> list[dict]:
    """
    params MUST include user_id filter (e.g. {"id": "eq.<id>", "user_id": "eq.<uuid>"}).
    """
    if not any(k == "user_id" for k in params):
        raise RuntimeError(f"db_update on '{table}' called without a user_id filter — refusing.")
    async with httpx.AsyncClient() as client:
        resp = await client.patch(
            f"{settings.SUPABASE_REST_URL}/{table}",
            headers=_service_headers({"Prefer": "return=representation"}),
            params=params,
            json=patch,
            timeout=30.0,
        )
    if resp.status_code >= 400:
        raise HTTPException(status_code=500, detail=f"DB update error on {table}: {resp.text}")
    return resp.json()


async def db_delete(table: str, params: dict) -> list[dict]:
    if not any(k == "user_id" for k in params):
        raise RuntimeError(f"db_delete on '{table}' called without a user_id filter — refusing.")
    async with httpx.AsyncClient() as client:
        resp = await client.delete(
            f"{settings.SUPABASE_REST_URL}/{table}",
            headers=_service_headers({"Prefer": "return=representation"}),
            params=params,
            timeout=30.0,
        )
    if resp.status_code >= 400:
        raise HTTPException(status_code=500, detail=f"DB delete error on {table}: {resp.text}")
    return resp.json()


async def rpc(function_name: str, payload: dict) -> list[dict] | dict:
    """For calling Postgres functions, e.g. vector similarity search."""
    async with httpx.AsyncClient() as client:
        resp = await client.post(
            f"{settings.SUPABASE_REST_URL}/rpc/{function_name}",
            headers=_service_headers(),
            json=payload,
            timeout=30.0,
        )
    if resp.status_code >= 400:
        raise HTTPException(status_code=500, detail=f"RPC error on {function_name}: {resp.text}")
    return resp.json()


# ---------------------------------------------------------------------
# Auth (uses ANON/publishable key — this is what Supabase Auth expects
# for signup/login/token-verification calls, not the service key)
# ---------------------------------------------------------------------

async def auth_signup(email: str, password: str) -> dict:
    async with httpx.AsyncClient() as client:
        resp = await client.post(
            f"{settings.SUPABASE_AUTH_URL}/signup",
            headers={"apikey": settings.SUPABASE_ANON_KEY, "Content-Type": "application/json"},
            json={"email": email, "password": password},
            timeout=30.0,
        )
    if resp.status_code >= 400:
        raise HTTPException(status_code=400, detail=resp.json().get("msg") or resp.text)
    return resp.json()


async def auth_login(email: str, password: str) -> dict:
    async with httpx.AsyncClient() as client:
        resp = await client.post(
            f"{settings.SUPABASE_AUTH_URL}/token?grant_type=password",
            headers={"apikey": settings.SUPABASE_ANON_KEY, "Content-Type": "application/json"},
            json={"email": email, "password": password},
            timeout=30.0,
        )
    if resp.status_code >= 400:
        raise HTTPException(status_code=401, detail=resp.json().get("error_description") or resp.text)
    return resp.json()


async def auth_get_user(access_token: str) -> dict:
    """Validates a JWT by asking Supabase who it belongs to. Raises 401 if invalid/expired."""
    async with httpx.AsyncClient() as client:
        resp = await client.get(
            f"{settings.SUPABASE_AUTH_URL}/user",
            headers={
                "apikey": settings.SUPABASE_ANON_KEY,
                "Authorization": f"Bearer {access_token}",
            },
            timeout=30.0,
        )
    if resp.status_code >= 400:
        raise HTTPException(status_code=401, detail="Invalid or expired session. Please log in again.")
    return resp.json()
