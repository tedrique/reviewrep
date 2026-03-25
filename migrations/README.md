# Alembic Migrations

Run locally:
```bash
alembic upgrade head
```

Env var `DATABASE_URL` is used; falls back to SQLite at `data/reviewbot.db`.
