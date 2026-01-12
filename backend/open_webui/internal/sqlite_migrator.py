import json
import logging
import sqlite3
from datetime import datetime
from pathlib import Path
from typing import Iterable

from sqlalchemy import Column, JSON, MetaData, Table, create_engine, func, select, text
from sqlalchemy.engine import Engine
from sqlalchemy.exc import SQLAlchemyError

from open_webui.env import (
    SRC_LOG_LEVELS,
    DATABASE_SQLITE_PATH,
    DATABASE_SCHEMA,
)
from open_webui.internal.db import JSONField

log = logging.getLogger(__name__)
log.setLevel(SRC_LOG_LEVELS["DB"])


def _should_run(sqlite_path: Path, target_engine: Engine) -> bool:
    if target_engine.name != "postgresql":
        return False
    if not sqlite_path.exists():
        log.info("SQLite migration skipped: source file %s not found", sqlite_path)
        return False
    return True


def _iter_tables(metadata: MetaData, available: set[str]) -> Iterable[Table]:
    for table in metadata.sorted_tables:
        if table.name == "alembic_version":
            continue
        if table.name not in available:
            continue
        yield table


def _refresh_sequences(target_engine: Engine, tables: Iterable[Table]) -> None:
    with target_engine.begin() as conn:
        for table in tables:
            pk_cols = [col for col in table.columns if col.primary_key]
            if not pk_cols:
                continue
            int_pk_cols = []
            for col in pk_cols:
                python_type = getattr(col.type, "python_type", None)
                if python_type is int:
                    int_pk_cols.append(col)
            if not int_pk_cols:
                continue
            pk_col = int_pk_cols[0]
            table_identifier = (
                f"{table.schema}.{table.name}" if table.schema else table.name
            )
            stmt = text(
                f"""
                SELECT setval(
                    pg_get_serial_sequence(:table_name, :pk_name),
                    COALESCE((SELECT MAX({pk_col.name}) FROM {table_identifier}), 0),
                    true
                )
                """
            )
            try:
                conn.execute(
                    stmt, {"table_name": table_identifier, "pk_name": pk_col.name}
                )
            except SQLAlchemyError as exc:
                log.warning(
                    "Failed to refresh sequence for %s.%s: %s",
                    table_identifier,
                    pk_col.name,
                    exc,
                )


def _quote_identifier(identifier: str) -> str:
    escaped = identifier.replace('"', '""')
    return f'"{escaped}"'


def _normalize_value(column: Column, value):
    if value is None:
        return None

    python_type = getattr(column.type, "python_type", None)
    if python_type is datetime:
        if isinstance(value, (int, float)):
            try:
                return datetime.fromtimestamp(value)
            except Exception:
                return value
        if isinstance(value, str):
            try:
                return datetime.fromisoformat(value)
            except ValueError:
                return value

    if isinstance(column.type, JSON) or isinstance(column.type, JSONField):
        if isinstance(value, str):
            try:
                return json.loads(value)
            except json.JSONDecodeError:
                return value
    return value


def _extract_rows(raw_conn: sqlite3.Connection, sqlite_table: Table, target_table: Table) -> list[dict]:
    columns = [col.name for col in sqlite_table.columns]
    column_clause = ", ".join(_quote_identifier(col) for col in columns)
    table_name = _quote_identifier(sqlite_table.name)
    cursor = raw_conn.execute(f"SELECT {column_clause} FROM {table_name}")
    target_columns = {col.name: col for col in target_table.columns}
    rows = []
    for row in cursor.fetchall():
        row_dict = {}
        for col_name in columns:
            value = row[col_name]
            target_col = target_columns.get(col_name)
            if target_col is not None:
                value = _normalize_value(target_col, value)
            row_dict[col_name] = value
        rows.append(row_dict)
    return rows


def migrate_sqlite_to_postgres(target_engine: Engine, dry_run: bool = False) -> bool:
    sqlite_path = Path(DATABASE_SQLITE_PATH)
    if not _should_run(sqlite_path, target_engine):
        return False

    sqlite_url = f"sqlite:///{sqlite_path}"
    sqlite_engine = create_engine(sqlite_url)

    target_metadata = MetaData(schema=DATABASE_SCHEMA)

    try:
        sqlite_metadata = MetaData()
        sqlite_metadata.reflect(bind=sqlite_engine)
    except (SQLAlchemyError, sqlite3.Error) as exc:
        log.error("SQLite migration aborted: unable to reflect source DB: %s", exc)
        return False

    try:
        target_metadata.reflect(bind=target_engine)
    except SQLAlchemyError as exc:
        if dry_run:
            log.debug(
                "Target metadata reflection failed during migration check: %s", exc
            )
            return True
        log.error("SQLite migration aborted: unable to reflect target DB: %s", exc)
        return False

    available_tables = set(sqlite_metadata.tables.keys())
    target_tables = list(_iter_tables(target_metadata, available_tables))

    if not target_tables:
        log.info("SQLite migration skipped: no overlapping tables detected")
        return False

    migrated_tables: list[Table] = []

    try:
        with sqlite3.connect(sqlite_path) as raw_conn, target_engine.connect() as target_read_conn:
            raw_conn.row_factory = sqlite3.Row
            for table in target_tables:
                sqlite_table = Table(
                    table.name,
                    MetaData(),
                    autoload_with=sqlite_engine,
                )

                source_count = raw_conn.execute(
                    f"SELECT COUNT(*) FROM {_quote_identifier(sqlite_table.name)}"
                ).fetchone()[0]
                if not source_count:
                    continue

                try:
                    existing_count = target_read_conn.execute(
                        select(func.count()).select_from(table)
                    ).scalar()
                except SQLAlchemyError:
                    existing_count = 0

                if existing_count and existing_count > 0:
                    if not dry_run:
                        log.info(
                            "Skipping table %s: target already has %s rows",
                            table.name,
                            existing_count,
                        )
                    continue

                if dry_run:
                    return True

                rows = _extract_rows(raw_conn, sqlite_table, table)
                if not rows:
                    continue

                with target_engine.begin() as target_write_conn:
                    target_write_conn.execute(table.insert(), rows)
                migrated_tables.append(table)
                log.info(
                    "Migrated %s rows into %s from SQLite", len(rows), table.name
                )
    except (SQLAlchemyError, sqlite3.Error) as exc:
        if dry_run:
            log.error("SQLite migration pre-check failed: %s", exc)
            return False
        log.error("SQLite migration failed: %s", exc)
        return False
    finally:
        sqlite_engine.dispose()

    if dry_run:
        return False

    if migrated_tables:
        _refresh_sequences(target_engine, migrated_tables)
        log.info(
            "SQLite migration completed for tables: %s",
            ", ".join(table.name for table in migrated_tables),
        )
        return True

    log.info("SQLite migration finished: no data copied")
    return False


__all__ = ["migrate_sqlite_to_postgres"]
