from fastapi.testclient import TestClient
from app.main import app
from scripts.seed_example import main as seed
client = TestClient(app)
def test_health():
    assert client.get("/health").json()["status"] == "ok"
def test_departments_after_seed():
    seed()
    r = client.get("/departments"); assert r.status_code == 200 and len(r.json()) == 11
    assert client.get("/departments/D99").status_code == 404
