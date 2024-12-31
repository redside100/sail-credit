import time
from typing import Any, Dict, List, Literal, Optional
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
        f"INSERT INTO users (discord_id, sail_credit) VALUES (?, {party.STARTING_SSC})",
        (discord_id,),
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


async def set_user(discord_id: int, sail_credit: int) -> None:
    await db.execute(
        "UPDATE users SET sail_credit = ? WHERE discord_id = ?",
        (sail_credit, discord_id),
    )
    await db.commit()


async def get_user_sail_credit_log(
    discord_id: int, start_timestamp: int, exclude_admin=False
) -> List[Dict[str, Any]]:

    exclude_clause = "AND source != 'ADMIN'" if exclude_admin else ""
    async with db.execute(
        f"SELECT * FROM sail_credit_log WHERE discord_id = ? AND timestamp > ? {exclude_clause} ORDER BY timestamp DESC",
        (discord_id, start_timestamp),
    ) as cursor:
        rows = await cursor.fetchall()
        return rows


async def change_and_log_sail_credit(
    discord_id: int,
    party_size: int,
    party_created_at: int,
    party_finished_at: int,
    old_ssc: int,
    new_ssc: int,
    source: Literal["PARTY", "ADMIN"] = "PARTY",
    timestamp: int = None,
) -> None:
    if not timestamp:
        timestamp = int(time.time())
    await db.execute(
        "INSERT INTO sail_credit_log VALUES (?, ?, ?, ?, ?, ?, ?, ?)",
        (
            discord_id,
            party_size,
            party_created_at,
            party_finished_at,
            old_ssc,
            new_ssc,
            source,
            timestamp,
        ),
    )
    await db.execute(
        "UPDATE users SET sail_credit = ? WHERE discord_id = ?", (new_ssc, discord_id)
    )
    await db.commit()


async def get_all_users() -> List[Dict[str, Any]]:
    async with db.execute("SELECT * FROM users") as cursor:
        rows = await cursor.fetchall()
        return rows


async def get_sail_credit_logs() -> List[Dict[str, Any]]:
    async with db.execute(
        "SELECT * FROM sail_credit_log ORDER BY timestamp ASC"
    ) as cursor:
        rows = await cursor.fetchall()
        return rows


async def clear_sail_credit_logs() -> None:
    await db.execute("DELETE FROM sail_credit_log")
    await db.commit()


async def get_ssc_leaderboard() -> List[Dict[str, Any]]:
    async with db.execute(
        "SELECT discord_id, sail_credit FROM users ORDER BY sail_credit DESC"
    ) as cursor:
        rows = await cursor.fetchall()
        return rows
