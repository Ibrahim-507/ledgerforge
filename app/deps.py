"""FastAPI glue for security. ONE dependency, `authorize`, runs before EVERY route (set once on the app) and uses the
permission table. Nobody can forget to protect a route: a route without a rule is refused by default."""
import os

from fastapi import Depends, HTTPException, Request
from fastapi.security import HTTPAuthorizationCredentials, HTTPBearer

from app.auth_store import user_from_token
from app.books_db import connect
from app.permissions import decide, is_public
from app.security import AuthError

bearer = HTTPBearer(auto_error=False)      # also gives the green "Authorize" button on /docs


def db_path() -> str:
    return os.environ.get("LEDGERFORGE_DB", "ledgerforge.sqlite")


def get_db():
    conn = connect(db_path(), check_same_thread=False)
    try:
        yield conn
    finally:
        conn.close()


def authorize(request: Request, creds: HTTPAuthorizationCredentials | None = Depends(bearer), conn=Depends(get_db)):
    route = request.scope.get("route")
    path = getattr(route, "path", request.url.path)         # the template, e.g. /employees/{employee_id}
    method = request.method
    user = None
    if not is_public(method, path) and creds is not None:
        try:
            user = user_from_token(conn, creds.credentials)
        except AuthError as e:
            raise HTTPException(status_code=401, detail=str(e), headers={"WWW-Authenticate": "Bearer"})
    verdict = decide(method, path, request.path_params, user)
    if verdict is not None:
        status, detail = verdict
        raise HTTPException(status_code=status, detail=detail,
                            headers={"WWW-Authenticate": "Bearer"} if status == 401 else None)
    request.state.user = user
