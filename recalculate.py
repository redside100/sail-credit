import uuid
import db
import asyncio
from sail_bank import SailBank
from party import Party, PartyMember, STARTING_SSC


bank = SailBank()


async def calculate():
    """
    This script reset the SSC for all users to their default values, and then
    recalculates the SSC for all users.
    """
    # Save all the logs into memory.
    existing_logs = await db.get_sail_credit_logs()

    # Reset all user to their starting SSC.
    for user in await db.get_all_users():
        await db.set_user(user["discord_id"], STARTING_SSC)

    # Wipe the logs table.
    await db.clear_sail_credit_logs()

    # Recalculate the SSC for all users.
    for log in existing_logs:
        party = Party(
            uuid=uuid.uuid4(),
            role=0,
            owner_id=0,
            name="",
            created_at=log["party_created_at"],
            finished_at=log["party_finished_at"],
            size=log["party_size"],
            members=[PartyMember(user_id=log["discord_id"], name="")],
        )
        if log["new_sail_credit"] - log["prev_sail_credit"] < 0:
            bank.process_flaked_user(party, log["discord_id"])
        else:
            bank.process_party_reward(party)


if __name__ == "__main__":
    asyncio.run(db.init())
    asyncio.run(calculate())
