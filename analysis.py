import asyncio
import json
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

    average_multiplier = 0
    over_eq_two_multiplier_count = 0
    async with db.db.execute(
        "SELECT * FROM casino_lobby_log WHERE game = 'CRASH'"
    ) as cursor:
        crash_logs = await cursor.fetchall()
        print(f"\nTotal Crash lobbies : {len(crash_logs)}")
        for log in crash_logs:
            metadata = json.loads(log["metadata"].decode())
            average_multiplier += metadata["crash_multiplier"]
            if metadata["crash_multiplier"] >= 2:
                over_eq_two_multiplier_count += 1

    if crash_logs:
        average_multiplier /= len(crash_logs)
        print(f"Average Multiplier : {average_multiplier:.2f}")

    print(f"Crashes >= 2x    : {over_eq_two_multiplier_count}")
    print(f"Crashes < 2x     : {len(crash_logs) - over_eq_two_multiplier_count}")

    await db.cleanup()


asyncio.run(main())
