import math
import time
from party import Party
import db
import party


class SailBank:
    """
    Welcome all.

    In calm currents flow,
    Sail Bank charts wealth's steady course—
    Dreams in safe harbors.
    """

    # How much sail credit a user receives for completing a party by default.
    BASE_REWARD = 20

    # How far back we check for previous parties, in seconds. Reward should be
    # decreased for each party joined within this time frame.
    LOOKBACK_WINDOW = 60 * 60 * 24  # 24 hours

    # How far back we check for previous flake incidents, in seconds.
    FLAKE_WINDOW = 60 * 60 * 24 * 30  # 30 days

    async def process(flake: bool):
        """
        Handles the process of calculating sail credit for a user based on whether they
        flaked on a party or not.
        """

        pass

    async def debit(
        self,
        user_id: int,
        current_ssc: int,
        flake_count: int,
        party_age: int,
        party_size: int,
    ):
        """
        Method for calculating how much sail credit to deduct to give to a user for
        flaking on a party.

        Input Parameters:
        - The user's current sail credit.
            - RATIONALE: The less SSC a user has, the less they lose on flake.
        - Number of incidents in the last N days where the user has flaked on a party.
            - RATIONALE: If a user consistently flakes over a period of time, they
            should lose more SSC. Checks last N days instead of parties to incentivize
            consistent behavior, and can't be erased by joining 20 parties in a day.
        - How long the party was established for before the user flaked.
            - RATIONALE: Discourages users from flaking on parties that have been
            established for a long time, when other people have invested more time into
            waiting.
        - The party's current size.
            - RATIONALE: The larger the party, the more people are affected by the
            flake.
        """
        print("-3")
        return -3

    async def credit(self, user_id: int, current_ssc: int, parties_joined: int):
        """
        Method for calculating how much sail credit to give to a user for not flaking
        on a party.

        Input Parameters:
        - The user's current sail credit.
            - RATIONALE: The more SSC a user has already, the less they gain.
        - The number of parties the user has participated in the past period.
            - RATIONALE: Subsequent parties in a day should not be as rewarding. This
            rewards consistency instead of just joining a bunch of parties in a day.
        """
        # The base reward for joining a party.
        reward = self.BASE_REWARD

        # Function to decrease the reward based on the number of parties joined within
        # the lookback period. Always round up. Returns a ratio.
        def diminishing_returns(parties_joined: int) -> float:
            return 1 / ((2 * parties_joined) + 1)

        # Taxes: makes it harder for users with more SSC to gain more. Returns a float
        # between 0 and 1. Returns a ratio.
        def taxes(current_ssc: int) -> float:
            return 1 - math.log(current_ssc + 1) / 10

        # Reduce the Base reward relative to how many parties the user has joined.
        diminishing_ratio = diminishing_returns(parties_joined)
        reward = math.ceil(reward * diminishing_ratio)

        # Only apply taxes if the user has more than starting SSC currently.
        tax_ratio = None
        if current_ssc > party.STARTING_SSC:
            tax_ratio = taxes(current_ssc)
            reward = math.ceil(reward * tax_ratio)

        log = (
            f"[user-{user_id}]: base-{self.BASE_REWARD} SSC"
            + f" * dim-{self._percent(diminishing_ratio)}%"
        )
        if tax_ratio:
            log += f" * tax-{self._percent(tax_ratio)}%"
        log += f" = {reward} SSC for joining a party."
        print(log)

        return reward

    async def process_party_reward(self, party: Party) -> dict[str, dict[str, int]]:
        """
        Process the reward for each player in the party. Returns a dictionary of user
        IDs and the amount of sail credit they received.
        """
        party_age = party.creation_time - int(time.time())

        data = {}
        for member in party.members:
            user = await db.get_user(member.user_id)
            data[member.user_id] = {"old": user["sail_credit"], "new": None}
            history = await db.get_user_sail_credit_log(
                member.user_id, self.LOOKBACK_WINDOW
            )
            reward = await self.credit(
                member.user_id, user["sail_credit"], len(history)
            )
            data[member.user_id]["new"] = user["sail_credit"] + reward
            await db.change_and_log_sail_credit(
                member.user_id,
                party.size,
                party_age,
                user["sail_credit"],
                user["sail_credit"] + reward,
            )
        return data

    async def process_flaked_user(self, party: Party, user_id: int) -> dict[str, int]:
        """
        Process the punishment for the user who flaked on the party. Returns how much
        SSC was deducted from the user.
        """
        user = await db.get_user(user_id)
        history = await db.get_user_sail_credit_log(user_id, self.FLAKE_WINDOW)
        party_age = party.creation_time - int(time.time())
        reward = await self.debit(
            user_id,
            user["sail_credit"],
            len(history),
            party_age,
            party.size,
        )
        await db.change_and_log_sail_credit(
            user_id,
            party.size,
            party_age,
            user["sail_credit"],
            user["sail_credit"] + reward,
        )
        return {
            "old": user["sail_credit"],
            "new": user["sail_credit"] + reward,
        }

    def _percent(self, x: float) -> float:
        return round(x * 100, 3)
