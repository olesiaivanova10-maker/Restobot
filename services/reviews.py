from pathlib import Path

import aiosqlite

from core.database import DATA_DIR

REVIEWS_DB = Path(DATA_DIR) / "reviews.db"


async def init_reviews_db() -> None:
    async with aiosqlite.connect(REVIEWS_DB) as conn:
        await conn.execute("""
            CREATE TABLE IF NOT EXISTS reviews (
                id INTEGER PRIMARY KEY,
                venue TEXT NOT NULL,
                body TEXT NOT NULL,
                chat_id INTEGER NOT NULL,
                prompt_id INTEGER NOT NULL,
                created_at TEXT NOT NULL DEFAULT CURRENT_TIMESTAMP,
                UNIQUE (chat_id, prompt_id)
            )
        """)
        await conn.commit()


async def save_review(venue: str, body: str, chat_id: int, prompt_id: int) -> None:
    async with aiosqlite.connect(REVIEWS_DB) as conn:
        await conn.execute(
            """
            INSERT INTO reviews (venue, body, chat_id, prompt_id)
            VALUES (?, ?, ?, ?)
            ON CONFLICT (chat_id, prompt_id) DO NOTHING
            """,
            (venue, body, chat_id, prompt_id),
        )
        await conn.commit()
