from fastapi import APIRouter, Depends, HTTPException, Request
from pydantic import BaseModel

from app.auth_store import login as do_login
from app.deps import get_db
from app.security import AuthError

router = APIRouter(prefix="/auth", tags=["auth"])


class LoginIn(BaseModel):
    username: str
    password: str


@router.post("/login")
def login(body: LoginIn, conn=Depends(get_db)):
    """Returns a token valid for 30 minutes. In /docs, click Authorize and paste the token."""
    try:
        return do_login(conn, body.username, body.password)
    except AuthError as e:
        raise HTTPException(status_code=401, detail=str(e), headers={"WWW-Authenticate": "Bearer"})


@router.get("/me")
def me(request: Request):
    return request.state.user
