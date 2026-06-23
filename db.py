from datetime import datetime, timezone
import time
from typing import Any, Dict, List, Optional
from zoneinfo import ZoneInfo
import aiosqlite

import party
import json

db = None


def dict_factory(cursor, row):
    d = {}
    for idx, col in enumerate(cursor.description):
        d[col[0]] = row[idx]
    return d


async def init():
    global db
    db = await aiosqlite.connect("sail_credit.db", timeout=5)
    db.row_factory = dict_factory


async def cleanup():
    global db
    if db and db.is_alive():
        await db.close()


async def run_migrations():
    with open("migrations.sql", "r") as f:
        script = f.read()
    await db.executescript(script)
    await db.commit()


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
    discord_id: int, start_timestamp: int, source: Optional[str] = "PARTY"
) -> List[Dict[str, Any]]:

    source_clause = ""
    if source:
        source_clause = "AND source = ?"
    async with db.execute(
        f"SELECT * FROM sail_credit_log WHERE discord_id = ? AND timestamp > ? {source_clause} ORDER BY timestamp DESC",
        (
            (discord_id, start_timestamp)
            if not source
            else (discord_id, start_timestamp, source)
        ),
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
    source: str = "PARTY",
    timestamp: Optional[int] = None,
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


async def log_convict_reason(discord_id: int, reason: str) -> None:
    now = int(time.time())
    await db.execute(
        "INSERT INTO conviction_log VALUES (?, ?, ?)", (discord_id, reason, now)
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


async def get_conviction_log(discord_id: Optional[int] = None) -> List[Dict[str, Any]]:
    if not discord_id:
        async with db.execute(
            "SELECT discord_id, reason, timestamp FROM conviction_log ORDER BY timestamp DESC"
        ) as cursor:
            rows = await cursor.fetchall()
            return rows

    async with db.execute(
        "SELECT discord_id, reason, timestamp FROM conviction_log WHERE discord_id = ? ORDER BY timestamp DESC",
        (discord_id,),
    ) as cursor:
        rows = await cursor.fetchall()
        return rows


async def update_role_image_url(role_id: int, image_url: Optional[str]) -> None:
    if image_url is None:
        await db.execute("DELETE FROM role_images WHERE role_id = ?", (role_id,))
    else:
        await db.execute(
            "INSERT OR REPLACE INTO role_images VALUES (?, ?)", (role_id, image_url)
        )
    await db.commit()


async def get_role_image_url(role_id: int) -> Optional[str]:
    async with db.execute(
        "SELECT image_url FROM role_images WHERE role_id = ?", (role_id,)
    ) as cursor:
        row = await cursor.fetchone()
        if not row:
            return None

        return row["image_url"]


async def create_casino_lobby_log(
    uuid: str, start_time: int, end_time: int, metadata: Dict[str, Any], game: str
):
    await db.execute(
        "INSERT INTO casino_lobby_log VALUES (?, ?, ?, ?, ?)",
        (uuid, start_time, end_time, json.dumps(metadata).encode(), game),
    )
    await db.commit()


async def get_casino_lobby_logs(game: str, limit: int = 10) -> Dict:
    async with db.execute(
        "SELECT * FROM casino_lobby_log WHERE game = ? ORDER BY start_time DESC LIMIT ?",
        (game, limit),
    ) as cursor:
        rows = await cursor.fetchall()
        return rows


def get_reset_time(timestamp: int) -> int:
    """
    Returns the day's reset timestamp of the given timestamp.
    """

    dt = datetime.fromtimestamp(timestamp, tz=timezone.utc).astimezone(
        ZoneInfo("America/New_York")
    )
    reset_time = dt.replace(hour=8, minute=0, second=0, microsecond=0)
    return reset_time.timestamp()


async def get_daily_reward_streak(user_id: int) -> int:
    """
    To be called BEFORE registering today's daily reward.
    """
    async with db.execute(
        "SELECT timestamp FROM sail_credit_log WHERE discord_id = ? AND source = ? ORDER BY timestamp DESC",
        (user_id, "DAILY_SSC"),
    ) as cursor:
        rows = await cursor.fetchall()

        if not rows:
            return 0

        now = int(datetime.now(timezone.utc).timestamp())
        expected_reset = int(get_reset_time(now)) - 86400  # yesterday's reset timestamp
        streak = 0
        for row in rows:
            row_reset = int(get_reset_time(row["timestamp"]))
            if row_reset > expected_reset:
                continue  # skip duplicate entries
            elif row_reset == expected_reset:
                streak += 1
                expected_reset -= 86400
            else:
                break

        return streak
