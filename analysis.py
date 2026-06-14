import asyncio
import time
import db


async def main():
    await db.init()

    async with db.db.execute(
        "SELECT * FROM sail_credit_log WHERE source LIKE 'CRASH_%' ORDER BY timestamp ASC"
    ) as cursor:
        logs = await cursor.fetchall()

    total_gained = 0
    total_lost = 0

    for log in logs:
        delta = log["new_sail_credit"] - log["prev_sail_credit"]
        if delta > 0:
            total_gained += delta
        else:
            total_lost += abs(delta)

    net = total_gained - total_lost
    print(f"Entries analysed : {len(logs)}")
    print(f"Total SSC gained : +{total_gained:,}")
    print(f"Total SSC lost   : -{total_lost:,}")
    print(f"Net SSC          : {'+' if net >= 0 else ''}{net:,}")

    await db.cleanup()


asyncio.run(main())
