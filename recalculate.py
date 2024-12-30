import uuid
import db
import asyncio
from scb import SailCreditBureau
from party import Party, PartyMember, STARTING_SSC


scb = SailCreditBureau()


async def calculate():
    """
    This script reset the SSC for all users to their default values, and then
    recalculates the SSC for all users.
    """
    # Save all the logs into memory.
    print("Fetching logs...")
    existing_logs = await db.get_sail_credit_logs()

    # Reset all user to their starting SSC.
    print("Resetting all users to default SSC...")
    for user in await db.get_all_users():
        await db.set_user(user["discord_id"], STARTING_SSC)

    # Wipe the logs table.
    print("Wiping the logs table...")
    await db.clear_sail_credit_logs()

    # Recalculate the SSC for all users.
    print("Recalculating SSC for all users...")
    print(f"Total logs: {len(existing_logs)}")
    for log in existing_logs:
        party = Party(
            uuid=uuid.uuid4(),
            role=0,
            owner_id=0,
            name="",
            created_at=log["party_created_at"],
            finished_at=log["party_finished_at"],
            size=log["party_size"],
        )
        if log["new_sail_credit"] - log["prev_sail_credit"] < 0:
            await scb.process_flaked_user(
                party, log["discord_id"], timestamp=log["timestamp"]
            )
        else:
            await scb.process_party_member(
                party, log["discord_id"], timestamp=log["timestamp"]
            )
    print("Done!")


if __name__ == "__main__":
    asyncio.run(db.init())
    asyncio.run(calculate())
