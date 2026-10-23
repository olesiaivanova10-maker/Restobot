import asyncio
import json

from core.logger import logger
from services.google_sheets import update_google_sheet
from services.sync_queue import (
    list_due_sheet_syncs,
    mark_sheet_sync_failed,
    remove_sheet_sync,
)


_worker_lock = asyncio.Lock()


async def process_pending_sheet_syncs(is_test: bool = False) -> None:
    if _worker_lock.locked():
        return

    async with _worker_lock:
        pending = await list_due_sheet_syncs(is_test=is_test)
        for item in pending:
            try:
                await asyncio.to_thread(
                    update_google_sheet,
                    item["sheet_name"],
                    item["report_type"],
                    json.loads(item["payload_json"]),
                    item["target_date"],
                )
                await remove_sheet_sync(
                    item["sheet_name"],
                    item["report_type"],
                    item["target_date"],
                    is_test=is_test,
                )
                logger.info(
                    f"Отложенная синхронизация завершена: "
                    f"{item['sheet_name']} {item['report_type']} {item['target_date']}"
                )
            except Exception as error:
                await mark_sheet_sync_failed(
                    item["id"],
                    error,
                    int(item["attempts"]) + 1,
                    is_test=is_test,
                )
