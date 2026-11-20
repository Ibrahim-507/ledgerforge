"""Users, login and token checking. Plain Python on the books database, so it is easy to test."""
from datetime import datetime
import pandas as pd
from app.security import AuthError, create_token, decode_token, hash_password, verify_password

_DUMMY_HASH = None


def seed_users(conn, users_csv, demo_password, limit=None, active_only=False) -> int:
    """Load the demo users from users.csv. The CSV holds no passwords, so every demo user gets the SAME demo password,
    stored only as a salted hash. A real system would send each person a reset link instead."""
    df = pd.read_csv(users_csv)
    if active_only:
        df = df[df.is_active == "Y"]
    if limit:
        df = df.head(limit)
    n = 0
    for r in df.itertuples():
        if conn.execute("SELECT 1 FROM users WHERE user_id=?", (r.user_id,)).fetchone():
            continue
        conn.execute("INSERT INTO users VALUES (?,?,?,?,?,?,?,?,?)",
                     (r.user_id, r.employee_id, r.username, hash_password(demo_password), r.role, r.is_active,
                      r.mfa_enabled, None if pd.isna(r.last_login_at) else str(r.last_login_at), str(r.created_at)))
        n += 1
    conn.commit()
    return n


def add_user(conn, user_id, username, password, role, employee_id=None, is_active="Y"):
    conn.execute("INSERT INTO users(user_id, employee_id, username, password_hash, role, is_active, created_at) VALUES (?,?,?,?,?,?,?)",
                 (user_id, employee_id, username, hash_password(password), role, is_active, datetime.now().strftime("%Y-%m-%d")))
    conn.commit()


def get_user(conn, user_id):
    r = conn.execute("SELECT user_id, employee_id, username, role, is_active FROM users WHERE user_id=?", (user_id,)).fetchone()
    return dict(r) if r else None


def set_active(conn, user_id, active: bool):
    conn.execute("UPDATE users SET is_active=? WHERE user_id=?", ("Y" if active else "N", user_id))
    conn.commit()


def authenticate(conn, username, password) -> dict:
    """Check a username and password. The error is always the same, so an attacker cannot learn which usernames exist."""
    global _DUMMY_HASH
    r = conn.execute("SELECT * FROM users WHERE username=?", (username,)).fetchone()
    if r is None:                                   # spend the same time as a real check
        _DUMMY_HASH = _DUMMY_HASH or hash_password("not-a-real-password")
        verify_password(password, _DUMMY_HASH)
        raise AuthError("Invalid username or password")
    if not verify_password(password, r["password_hash"]) or r["is_active"] != "Y":
        raise AuthError("Invalid username or password")
    conn.execute("UPDATE users SET last_login_at=? WHERE user_id=?", (datetime.now().strftime("%Y-%m-%d %H:%M:%S"), r["user_id"]))
    conn.commit()
    return get_user(conn, r["user_id"])


def login(conn, username, password) -> dict:
    user = authenticate(conn, username, password)
    return {"access_token": create_token(user), "token_type": "bearer", "expires_in": 30 * 60,
            "user_id": user["user_id"], "role": user["role"]}


def user_from_token(conn, token) -> dict:
    """Who is making this request? The token proves identity; the DATABASE decides role and whether the account is active.
    Rule (think-for-yourself): a user deactivated while holding a valid token is refused on their very next request."""
    claims = decode_token(token)
    user = get_user(conn, claims["sub"])
    if user is None or user["is_active"] != "Y":
        raise AuthError("Account is deactivated or does not exist")
    return user
