import json
from datetime import timedelta

from sqlalchemy import text

from core.config import now_vlad
from core.database import AsyncSessionLocal, AsyncSessionLocalTest
from core.logger import logger


def _session(is_test: bool):
    return AsyncSessionLocalTest() if is_test else AsyncSessionLocal()


async def enqueue_sheet_sync(
    sheet_name: str,
    report_type: str,
    target_date: str,
    collected_data: dict,
    is_test: bool = False,
) -> None:
    now = now_vlad()
    async with _session(is_test) as session:
        await session.execute(
            text("""
                INSERT INTO sheet_sync_queue
                    (sheet_name, report_type, target_date, payload_json, is_test,
                     attempts, next_attempt_at, last_error, created_at)
                VALUES
                    (:sheet_name, :report_type, :target_date, :payload_json, :is_test,
                     0, :next_attempt_at, '', :created_at)
                ON CONFLICT(sheet_name, report_type, target_date) DO UPDATE SET
                    payload_json = excluded.payload_json,
                    is_test = excluded.is_test,
                    next_attempt_at = excluded.next_attempt_at,
                    last_error = ''
            """),
            {
                "sheet_name": sheet_name,
                "report_type": report_type,
                "target_date": target_date,
                "payload_json": json.dumps(collected_data, ensure_ascii=False),
                "is_test": int(is_test),
                "next_attempt_at": now.isoformat(),
                "created_at": now.isoformat(),
            },
        )
        await session.commit()


async def remove_sheet_sync(
    sheet_name: str,
    report_type: str,
    target_date: str,
    is_test: bool = False,
) -> None:
    async with _session(is_test) as session:
        await session.execute(
            text("""
                DELETE FROM sheet_sync_queue
                WHERE sheet_name = :sheet_name
                  AND report_type = :report_type
                  AND target_date = :target_date
            """),
            {
                "sheet_name": sheet_name,
                "report_type": report_type,
                "target_date": target_date,
            },
        )
        await session.commit()


async def list_due_sheet_syncs(is_test: bool = False) -> list[dict]:
    now = now_vlad().isoformat()
    async with _session(is_test) as session:
        result = await session.execute(
            text("""
                SELECT id, sheet_name, report_type, target_date, payload_json,
                       is_test, attempts
                FROM sheet_sync_queue
                WHERE next_attempt_at <= :now
                ORDER BY id
                LIMIT 20
            """),
            {"now": now},
        )
        return [dict(row) for row in result.mappings().all()]


async def mark_sheet_sync_failed(sync_id: int, error: Exception, attempts: int, is_test: bool = False) -> None:
    delay_minutes = min(60, 2 ** min(attempts, 5))
    next_attempt = now_vlad() + timedelta(minutes=delay_minutes)
    async with _session(is_test) as session:
        await session.execute(
            text("""
                UPDATE sheet_sync_queue
                SET attempts = :attempts,
                    next_attempt_at = :next_attempt_at,
                    last_error = :last_error
                WHERE id = :id
            """),
            {
                "id": sync_id,
                "attempts": attempts,
                "next_attempt_at": next_attempt.isoformat(),
                "last_error": str(error)[-2000:],
            },
        )
        await session.commit()
    logger.warning(
        f"Синхронизация Sheets отложена: id={sync_id}, "
        f"следующая попытка через {delay_minutes} мин.: {error}"
    )
