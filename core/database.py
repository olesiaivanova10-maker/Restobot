import os
import json
from sqlalchemy.ext.asyncio import create_async_engine, async_sessionmaker
from sqlalchemy import text
from sqlalchemy.orm import declarative_base

from core.logger import logger
from core.config import OPEN_FIELD_MAP, CLOSE_FIELD_MAP

# Use /app/data if it exists (Docker), else use local ./data
DATA_DIR = "/app/data" if os.path.exists("/app/data") else os.path.join(os.path.dirname(os.path.dirname(os.path.abspath(__file__))), "data")
os.makedirs(DATA_DIR, exist_ok=True)

DATABASE_URL = f"sqlite+aiosqlite:///{os.path.join(DATA_DIR, 'restobot.db')}"
TEST_DATABASE_URL = f"sqlite+aiosqlite:///{os.path.join(DATA_DIR, 'test_restobot.db')}"

engine = create_async_engine(DATABASE_URL, echo=False)
test_engine = create_async_engine(TEST_DATABASE_URL, echo=False)

AsyncSessionLocal = async_sessionmaker(engine, expire_on_commit=False)
AsyncSessionLocalTest = async_sessionmaker(test_engine, expire_on_commit=False)
Base = declarative_base()

SHEET_SYNC_COLUMNS = {
    "sheet_name": "VARCHAR NOT NULL",
    "report_type": "VARCHAR NOT NULL",
    "target_date": "VARCHAR NOT NULL",
    "payload_json": "TEXT NOT NULL",
    "is_test": "BOOLEAN DEFAULT 0",
    "attempts": "INTEGER DEFAULT 0",
    "next_attempt_at": "VARCHAR NOT NULL",
    "last_error": "TEXT DEFAULT ''",
    "created_at": "VARCHAR NOT NULL",
}

SHIFT_COLUMNS = {
    "is_opened": "BOOLEAN DEFAULT 0",
    "open_time": "VARCHAR DEFAULT ''",
    "open_stop_list": "VARCHAR DEFAULT ''",
    "open_products": "VARCHAR DEFAULT ''",
    "open_household": "VARCHAR DEFAULT ''",
    "open_report": "VARCHAR DEFAULT ''",
    "is_closed": "BOOLEAN DEFAULT 0",
    "close_time": "VARCHAR DEFAULT ''",
    "close_cash": "VARCHAR DEFAULT ''",
    "close_card": "VARCHAR DEFAULT ''",
    "close_deposits": "VARCHAR DEFAULT ''",
    "close_revenue": "VARCHAR DEFAULT ''",
    "close_guests": "VARCHAR DEFAULT ''",
    "close_dangerous": "VARCHAR DEFAULT ''",
    "close_comps": "VARCHAR DEFAULT ''",
    "close_marketing": "VARCHAR DEFAULT ''",
    "close_expenses": "VARCHAR DEFAULT ''",
    "close_meduza": "VARCHAR DEFAULT ''",
    "close_report": "VARCHAR DEFAULT ''",
}

def _stringify_report_value(value):
    if value is None:
        return ""
    if isinstance(value, dict):
        value = value.get("value") or value.get("text") or value.get("status") or ""
    return str(value)

async def migrate_shift_schema(conn):
    rows = await conn.execute(text("PRAGMA table_info(shifts)"))
    existing_columns = {row[1] for row in rows.fetchall()}
    if not existing_columns:
        return

    missing_columns = [
        (name, ddl)
        for name, ddl in SHIFT_COLUMNS.items()
        if name not in existing_columns
    ]

    for name, ddl in missing_columns:
        await conn.execute(text(f"ALTER TABLE shifts ADD COLUMN {name} {ddl}"))

    if missing_columns:
        logger.info(
            f"SQLite schema migrated: added columns {', '.join(name for name, _ in missing_columns)}"
        )

    if "report_data" not in existing_columns:
        return

    result = await conn.execute(
        text("SELECT id, is_opened, is_closed, report_data FROM shifts WHERE report_data IS NOT NULL")
    )

    for row in result.mappings():
        try:
            report_data = row["report_data"]
            if isinstance(report_data, str):
                report_data = json.loads(report_data)
            if not isinstance(report_data, dict):
                continue

            values = {}
            for metric_name, column_name in {**OPEN_FIELD_MAP, **CLOSE_FIELD_MAP}.items():
                if metric_name in report_data:
                    values[column_name] = _stringify_report_value(report_data[metric_name])

            if row["is_opened"] and not values.get("open_time"):
                values["open_time"] = report_data.get("open_time") or report_data.get("Время открытия") or "Да"
            if row["is_closed"] and not values.get("close_time"):
                values["close_time"] = report_data.get("close_time") or report_data.get("Время закрытия") or "Да"

            if not values:
                continue

            assignments = ", ".join(f"{column_name} = :{column_name}" for column_name in values)
            await conn.execute(
                text(f"UPDATE shifts SET {assignments} WHERE id = :id"),
                {**values, "id": row["id"]},
            )
        except Exception as exc:
            logger.warning(f"Could not migrate report_data for shift id={row['id']}: {exc}")

async def init_db():
    async with engine.begin() as conn:
        await conn.run_sync(Base.metadata.create_all)
        await migrate_shift_schema(conn)
        await migrate_sheet_sync_schema(conn)
        
    async with test_engine.begin() as conn:
        await conn.run_sync(Base.metadata.create_all)
        await migrate_shift_schema(conn)
        await migrate_sheet_sync_schema(conn)


async def migrate_sheet_sync_schema(conn):
    await conn.execute(text("""
        CREATE TABLE IF NOT EXISTS sheet_sync_queue (
            id INTEGER PRIMARY KEY AUTOINCREMENT,
            sheet_name VARCHAR NOT NULL,
            report_type VARCHAR NOT NULL,
            target_date VARCHAR NOT NULL,
            payload_json TEXT NOT NULL,
            is_test BOOLEAN DEFAULT 0,
            attempts INTEGER DEFAULT 0,
            next_attempt_at VARCHAR NOT NULL,
            last_error TEXT DEFAULT '',
            created_at VARCHAR NOT NULL,
            UNIQUE(sheet_name, report_type, target_date)
        )
    """))
