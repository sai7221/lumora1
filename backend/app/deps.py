"""
Dependency used by every protected route to get the current user.
Extracts the Bearer token, asks Supabase to validate it, and returns
the user's id + email. Every router uses this to scope DB queries.
"""
from fastapi import Header, HTTPException
from .supabase_client import auth_get_user


async def get_current_user(authorization: str | None = Header(default=None)) -> dict:
    if not authorization or not authorization.lower().startswith("bearer "):
        raise HTTPException(status_code=401, detail="Missing or malformed Authorization header.")
    token = authorization.split(" ", 1)[1].strip()
    user = await auth_get_user(token)
    if "id" not in user:
        raise HTTPException(status_code=401, detail="Could not resolve user from token.")
    return {"id": user["id"], "email": user.get("email")}
