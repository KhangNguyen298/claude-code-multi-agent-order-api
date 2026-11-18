# Order API Demo

A small REST API to manage orders, built by a team of 4 subagents.

## Tech stack
- Python 3.11+, FastAPI, Pydantic v2, SQLAlchemy 2.x, SQLite, pytest

## Agent pipeline (always follow this order)
1. `architect` -> writes docs/architecture.md and docs/api-contract.yaml
2. `database`  -> writes docs/data-model.md and app/models, app/db
3. `backend`   -> writes app/schemas, app/services, app/api, app/main.py
4. `qa`        -> writes tests/ and docs/qa-report.md

If `qa` reports bugs, send them back to `backend`, then run `qa` again.
Repeat at most 2 times.

## How agents communicate
Agents never rely on chat memory. Each agent reads the previous agents' files in
`docs/` and writes its own `docs/handoff-<agent>.md` when done.

## Commands
- Install: `pip install -r requirements.txt`
- Seed DB: `python -m app.db.seed`
- Run API: `uvicorn app.main:app --reload` (docs at http://127.0.0.1:8000/docs)
- Test:    `pytest -q`
