"""Task 13: password hashing and login tokens.
* Passwords are hashed with scrypt (memory-hard) and a random salt per user. We never store or log a password.
* Tokens are JWT (HS256) that expire after 30 minutes. The secret key comes from the ENVIRONMENT, never from code.
Set the key once per terminal session:
    PowerShell:  $env:LEDGERFORGE_SECRET_KEY = python -c "import secrets; print(secrets.token_urlsafe(48))" """
import base64
import hashlib
import hmac
import os
import secrets
from datetime import datetime, timedelta, timezone

import jwt  # PyJWT

TOKEN_MINUTES = 30
ALGORITHM = "HS256"
SCRYPT_N, SCRYPT_R, SCRYPT_P = 2 ** 14, 8, 1
MIN_PASSWORD_LENGTH = 8


class AuthError(Exception):
    """Login or token problem: the caller must answer 401."""


class ConfigError(RuntimeError):
    """The server is not configured safely (for example no secret key)."""


def get_secret() -> str:
    key = os.environ.get("LEDGERFORGE_SECRET_KEY", "")
    if len(key) < 32:
        raise ConfigError("Set the environment variable LEDGERFORGE_SECRET_KEY to a random string of at least 32 characters")
    return key


# ---------------- passwords ---------------------------------------------------------------------
def _b64(b: bytes) -> str:
    return base64.b64encode(b).decode()


def hash_password(password: str) -> str:
    if not isinstance(password, str) or len(password) < MIN_PASSWORD_LENGTH:
        raise ValueError(f"Password must be at least {MIN_PASSWORD_LENGTH} characters")
    salt = os.urandom(16)
    h = hashlib.scrypt(password.encode(), salt=salt, n=SCRYPT_N, r=SCRYPT_R, p=SCRYPT_P, dklen=32)
    return f"scrypt${SCRYPT_N}${SCRYPT_R}${SCRYPT_P}${_b64(salt)}${_b64(h)}"


def verify_password(password: str, stored: str) -> bool:
    try:
        scheme, n, r, p, salt, want = stored.split("$")
        if scheme != "scrypt":
            return False
        got = hashlib.scrypt(password.encode(), salt=base64.b64decode(salt), n=int(n), r=int(r), p=int(p), dklen=32)
        return hmac.compare_digest(got, base64.b64decode(want))
    except Exception:
        return False


# ---------------- tokens ------------------------------------------------------------------------------
def create_token(user: dict, minutes: int = TOKEN_MINUTES, now: datetime | None = None, secret: str | None = None) -> str:
    """The token only IDENTIFIES the user (sub). Role and active status are read from the database on every request."""
    now = now or datetime.now(timezone.utc)
    payload = {"sub": user["user_id"], "iat": now, "exp": now + timedelta(minutes=minutes), "jti": secrets.token_hex(8)}
    return jwt.encode(payload, secret or get_secret(), algorithm=ALGORITHM)


def decode_token(token: str, secret: str | None = None) -> dict:
    try:
        return jwt.decode(token, secret or get_secret(), algorithms=[ALGORITHM], leeway=5,
                          options={"require": ["exp", "sub"]})
    except jwt.ExpiredSignatureError:
        raise AuthError("Token expired: please log in again")
    except jwt.PyJWTError:
        raise AuthError("Invalid token")
