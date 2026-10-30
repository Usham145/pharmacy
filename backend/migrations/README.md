# Database migrations

The application currently keeps its lightweight compatibility migrations in
`backend/app/main.py` so existing SQLite demonstration databases continue to
open without a separate migration step. Before production schema changes,
capture a PostgreSQL backup and review the generated SQL against the deployed
database.

Recommended workflow:

1. Create a backup with `.\scripts\backup_postgres.ps1`.
2. Apply the application and allow the startup compatibility migration to run.
3. Check `GET /health` and verify the affected workflow.
4. Keep a dated backup until the release is accepted.

For a larger production deployment, these statements should be moved to a
versioned Alembic migration history rather than adding more startup checks.
