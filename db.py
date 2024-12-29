import time
from typing import Any, Dict, List, Optional
import aiosqlite

import party

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
        "INSERT INTO users (discord_id, sail_credit) VALUES (?, 600)", (discord_id,)
    )
    await db.commit()
    return {"discord_id": discord_id, "sail_credit": party.STARTING_SSC}


async def get_user(discord_id: int) -> Optional[Dict[str, Any]]:
    async with db.execute(
        "SELECT * FROM users WHERE discord_id = ?", (discord_id,)
    ) as cursor:
        row = await cursor.fetchone()
        if not row:
            return None

        return row


async def get_user_sail_credit_log(
    discord_id: int, lookback: int
) -> List[Dict[str, Any]]:
    timestamp = int(time.time())

    earliest_timestamp = timestamp - lookback
    async with db.execute(
        "SELECT * FROM sail_credit_log WHERE discord_id = ? AND timestamp > ? ORDER BY timestamp DESC",
        (discord_id, earliest_timestamp),
    ) as cursor:
        rows = await cursor.fetchall()
        return rows


async def change_and_log_sail_credit(
    discord_id: int, party_size: int, party_lifetime: int, old_ssc: int, new_ssc: int
) -> None:
    timestamp = int(time.time())
    await db.execute(
        "INSERT INTO sail_credit_log VALUES (?, ?, ?, ?, ?, ?)",
        (discord_id, party_size, party_lifetime, old_ssc, new_ssc, timestamp),
    )
    await db.execute(
        "UPDATE users SET sail_credit = ? WHERE discord_id = ?", (new_ssc, discord_id)
    )
    await db.commit()
