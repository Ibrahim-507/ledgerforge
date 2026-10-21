# LedgerForge: starter project
This is a tiny, working skeleton. It already runs. You grow it into the full product over 4 weeks.

## First 10 minutes
```
python -m venv .venv
# Windows: .venv\Scripts\activate      Mac/Linux: source .venv/bin/activate
pip install -r requirements.txt
cp .env.example .env            # Windows: copy .env.example .env
python -m scripts.seed_example
uvicorn app.main:app --reload
```
Open http://127.0.0.1:8000/docs and try `GET /departments`. Run `pytest` to see the tests pass.

## What is already done for you (copy the pattern, do not just read it)
- `app/models.py` one table (Department)   - `app/routers/departments.py` one router
- `scripts/seed_example.py` one safe CSV loader   - `tests/` two working tests

## Rules
Never commit `.env`. One Git branch per task (`lf-02-employee-model`). Write a test for every new endpoint.
