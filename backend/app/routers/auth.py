from fastapi import APIRouter, Depends
from pydantic import BaseModel, EmailStr
from ..supabase_client import auth_signup, auth_login
from ..deps import get_current_user

router = APIRouter(prefix="/api/auth", tags=["auth"])


class Credentials(BaseModel):
    email: EmailStr
    password: str


@router.post("/signup")
async def signup(creds: Credentials):
    result = await auth_signup(creds.email, creds.password)
    # Supabase returns a user object; if email confirmation is ON, there's
    # no session yet. If you disabled "Confirm email" for testing, a
    # session/access_token will be included and you can log in right away.
    return {
        "message": "Signup successful. If email confirmation is enabled, check your inbox before logging in.",
        "user_id": result.get("id"),
        "session": result.get("session"),  # may be None if confirmation required
    }


@router.post("/login")
async def login(creds: Credentials):
    result = await auth_login(creds.email, creds.password)
    return {
        "access_token": result["access_token"],
        "refresh_token": result.get("refresh_token"),
        "user_id": result["user"]["id"],
        "email": result["user"]["email"],
    }


@router.get("/me")
async def me(user: dict = Depends(get_current_user)):
    """Protected test route — proves token verification works end-to-end."""
    return {"user_id": user["id"], "email": user["email"]}
