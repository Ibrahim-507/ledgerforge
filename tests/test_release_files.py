"""Release checks that need no Docker: they read the release files and make sure no secret can reach the image or the repository."""
import os
import re
import subprocess
import sys
import tempfile
from pathlib import Path

ROOT = Path(__file__).resolve().parent.parent


def read(name):
    return (ROOT / name).read_text(encoding="utf-8")


def test_dockerfile_has_no_secret_and_runs_as_a_normal_user():
    d = read("Dockerfile")
    assert not re.search(r"COPY[^\n]*\.env", d) and "COPY . ." in d              # .env is kept out by .dockerignore
    for line in d.splitlines():
        if line.strip().upper().startswith("ENV") or line.strip().upper().startswith("ARG"):
            assert not re.search(r"(SECRET|PASSWORD|TOKEN|KEY)\w*\s*=\s*\S", line.upper().replace("LEDGERFORGE_STATE_DIR", "")), line
    assert "USER appuser" in d and "HEALTHCHECK" in d and "requirements-prod.txt" in d and "scripts.entrypoint" in d


def test_dockerignore_keeps_secrets_and_databases_out_of_the_image():
    lines = [x.strip() for x in read(".dockerignore").splitlines()]
    for must in (".env", ".secret_key", "*.sqlite", ".git", "data", ".venv", "tests"):
        assert must in lines, must
    assert "seed" not in lines                                                     # the seed data must reach the image


def test_env_example_holds_only_placeholders():
    values = dict(l.split("=", 1) for l in read(".env.example").splitlines() if "=" in l and not l.startswith("#"))
    assert set(values) >= {"LEDGERFORGE_SECRET_KEY", "POSTGRES_PASSWORD", "DEMO_PASSWORD"}
    assert all("change-me" in v for v in values.values())


def test_compose_has_the_four_services_and_no_literal_secret():
    text = read("docker-compose.yml")
    for service in ("db:", "redis:", "api:", "worker:"):
        assert re.search(r"^  " + service, text, re.M), service
    for line in text.splitlines():
        if re.search(r"(PASSWORD|SECRET)", line) and not line.strip().startswith("#"):
            assert "${" in line, line                                              # secrets only as ${VARIABLES} read from .env
    assert "celery -A app.worker.celery_app" in text.replace('", "', " ").replace('"', "").replace("[", "").replace("]", "").replace(",", "")
    try:
        import yaml
    except ImportError:
        return
    c = yaml.safe_load(text)
    assert set(c["services"]) == {"db", "redis", "api", "worker"}
    assert c["services"]["api"]["depends_on"]["db"]["condition"] == "service_healthy"
    assert "8000:8000" in c["services"]["api"]["ports"] and "books" in c["volumes"]


def test_workflow_runs_tests_on_every_push_and_checks_the_image():
    text = read(".github/workflows/tests.yml")
    assert re.search(r"^on:\s*\n\s+push:\s*\n\s+pull_request:", text, re.M)
    assert "pytest -q --cov=app" in text and "docker build" in text and "cp -r seed data" in text
    assert "/app/.env" in text and "*.sqlite" in text


def test_gitignore_keeps_secrets_out_of_the_repository():
    path = ROOT / ".gitignore"
    if not path.exists():
        return
    lines = [x.strip() for x in path.read_text().splitlines()]
    assert ".env" in lines and ".secret_key" in lines and "*.sqlite" in lines


def test_requirements_cover_the_release_stack():
    r = read("requirements-prod.txt").lower()
    for pkg in ("fastapi", "uvicorn", "pyjwt", "pandas", "reportlab", "celery", "redis", "sqlalchemy", "psycopg"):
        assert pkg in r, pkg


def test_container_refuses_to_start_with_a_missing_or_example_secret():
    for secret in ("", "short", "change-me-run-the-command-above-0123456789abcdef"):
        env = {**os.environ, "LEDGERFORGE_SECRET_KEY": secret, "LEDGERFORGE_STATE_DIR": tempfile.mkdtemp()}
        r = subprocess.run([sys.executable, str(ROOT / "scripts" / "entrypoint.py")], cwd=ROOT, env=env, capture_output=True, text=True, timeout=60)
        assert r.returncode == 1 and "[FAIL]" in r.stdout and "LEDGERFORGE_SECRET_KEY" in r.stdout, (secret, r.stdout, r.stderr)


def test_make_seed_copies_the_csv_files():
    work = Path(tempfile.mkdtemp())
    (work / "data").mkdir()
    (work / "data" / "a.csv").write_text("x\n1\n")
    (work / "data" / "b.txt").write_text("ignore me")
    r = subprocess.run([sys.executable, str(ROOT / "scripts" / "make_seed.py")], cwd=work, capture_output=True, text=True, timeout=60)
    assert r.returncode == 0 and (work / "seed" / "a.csv").exists() and not (work / "seed" / "b.txt").exists()
