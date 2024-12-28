from typing import Any, Dict, Optional
import aiosqlite

db = None


def dict_factory(cursor, row):
    d = {}
    for idx, col in enumerate(cursor.description):
        d[col[0]] = row[idx]
    return d


async def init():
    global db
    db = await aiosqlite.connect("sail_credit.db")
    db.row_factory = dict_factory


async def cleanup():
    global db
    if db and db.is_alive():
        await db.close()


async def create_user(discord_id: int) -> Dict[str, Any]:
    await db.execute(
        "INSERT INTO users (discord_id, sail_credit) VALUES (?, 0)", (discord_id,)
    )
    await db.commit()
    return {"discord_id": discord_id, "sail_credit": 0}


async def get_user(discord_id: int) -> Optional[Dict[str, Any]]:
    async with db.execute(
        "SELECT * FROM users WHERE discord_id = ?", (discord_id,)
    ) as cursor:
        row = await cursor.fetchone()
        if not row:
            return None

        return row
