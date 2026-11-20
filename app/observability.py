"""JSON logs + /health that really tests the databases.
Install (2 lines at the END of app/main.py, after prefix_all(app)):
    from app.observability import install
    install(app)
/health is answered in middleware, so it needs no login."""
import json, logging, os, sqlite3, sys, time, uuid
from fastapi.responses import JSONResponse


class JsonFormatter(logging.Formatter):
    def format(self, record):
        d = {"time": self.formatTime(record, "%Y-%m-%dT%H:%M:%S"), "level": record.levelname,
             "logger": record.name, "message": record.getMessage()}
        d.update(getattr(record, "extra_fields", {}))
        return json.dumps(d)


def setup_logging():
    h = logging.StreamHandler(sys.stdout)
    h.setFormatter(JsonFormatter())
    root = logging.getLogger()
    root.handlers = [h]
    root.setLevel(os.environ.get("LOG_LEVEL", "INFO"))


def _books_path():
    p = os.environ.get("LEDGERFORGE_DB") or os.environ.get("LEDGERFORGE_BOOKS_PATH")
    if p:
        return p
    try:
        from app import books_db
        for n in ("DB_PATH", "DB_FILE", "DATABASE_PATH", "BOOKS_PATH", "PATH"):
            v = getattr(books_db, n, None)
            if v:
                return str(v)
    except Exception:
        pass
    return os.environ.get("LEDGERFORGE_BOOKS_PATH", "ledgerforge.sqlite")


def check_db():
    out = {}
    try:
        from pathlib import Path
        c = sqlite3.connect(Path(_books_path()).resolve().as_uri() + "?mode=rw", uri=True, timeout=3)
        c.execute("SELECT 1 FROM sqlite_master LIMIT 1").fetchall()
        c.close()
        out["books_sqlite"] = "ok"
    except Exception as e:
        out["books_sqlite"] = "FAIL: " + str(e)[:150]
    url = os.environ.get("DATABASE_URL")
    if url:
        try:
            from sqlalchemy import create_engine, text
            with create_engine(url, pool_pre_ping=True).connect() as conn:
                conn.execute(text("SELECT 1"))
            out["main_db"] = "ok"
        except Exception as e:
            out["main_db"] = "FAIL: " + str(e)[:150]
    return out


def install(app):
    setup_logging()
    log = logging.getLogger("ledgerforge.http")

    @app.middleware("http")
    async def _mw(request, call_next):
        if request.url.path == "/health":
            checks = check_db()
            ok = all(v == "ok" for v in checks.values())
            return JSONResponse({"status": "ok" if ok else "down", "checks": checks},
                                status_code=200 if ok else 503)
        rid = uuid.uuid4().hex[:8]
        t0 = time.perf_counter()
        resp = await call_next(request)
        ms = round((time.perf_counter() - t0) * 1000, 1)
        log.info("request", extra={"extra_fields": {
            "request_id": rid, "method": request.method, "path": request.url.path,
            "status": resp.status_code, "ms": ms}})
        resp.headers["X-Request-ID"] = rid
        return resp
