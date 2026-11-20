import json, logging
from fastapi.testclient import TestClient
from app.cache import ttl_cache
from app import observability
from app.main import app


def test_cache_returns_same_value_within_ttl():
    calls = []

    @ttl_cache(60)
    def f(x):
        calls.append(x)
        return x * 2

    assert f(2) == 4 and f(2) == 4
    assert len(calls) == 1


def test_cache_clear_forces_recompute():
    calls = []

    @ttl_cache(60)
    def f():
        calls.append(1)
        return 1

    f(); f.clear(); f()
    assert len(calls) == 2


def test_json_formatter_outputs_valid_json():
    rec = logging.LogRecord("x", logging.INFO, __file__, 1, "hello", None, None)
    d = json.loads(observability.JsonFormatter().format(rec))
    assert d["message"] == "hello" and d["level"] == "INFO"


def test_health_ok():
    r = TestClient(app).get("/health")
    assert r.status_code == 200 and r.json()["status"] == "ok"


def test_health_detects_database_failure(monkeypatch):
    monkeypatch.setattr(observability, "_books_path", lambda: "Z:/no_such_folder/x.sqlite")
    r = TestClient(app).get("/health")
    assert r.status_code == 503 and r.json()["status"] == "down"
