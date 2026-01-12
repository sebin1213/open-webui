"""Run Alembic migrations and SQLite→PostgreSQL data copy once before launch."""

from open_webui.config import run_migrations, log


def main() -> None:
    log.info("Starting manual database migration run")
    run_migrations()
    log.info("Database migrations completed")


if __name__ == "__main__":
    main()
