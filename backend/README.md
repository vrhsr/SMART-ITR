# SmartITR Backend

## Local run (dev)

Set env:

- `DATABASE_URL` (PostgreSQL), e.g. `postgresql+psycopg://user:pass@localhost:5432/smartitr`

Run:

- `python -m uvicorn main:app --reload --port 8000`

Migrations:

- `python -m alembic upgrade head`

