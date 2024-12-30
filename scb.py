import math
import time
from party import Party
import db
import party


class SailCreditBureau:
    """
    Welcome all.

    In Sail Bureau's care,
    Scores like stars, shining bright paths—
    Future steps secure.
    """

    # How much sail credit a user receives for completing a party by default.
    BASE_REWARD = 20

    # How much sail credit to deduct from a user for flaking on a party.
    BASE_PENALTY = -200

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
        - How long the party was established for before the user flaked (in seconds).
            - RATIONALE: Discourages users from flaking on parties that have been
            established for a long time, when other people have invested more time into
            waiting.
        - The party's current size.
            - RATIONALE: The larger the party, the more people are affected by the
            flake.
        """
        # 1. The base SSC to deduct for flaking.
        penalty = self.BASE_PENALTY
        log = f"[user-{user_id}]: DEBIT base:{self.BASE_PENALTY} SSC "

        # 2. Punish based on how many people were affected.
        # (less than group of 5 = < 20% reduction) / (more than group of 5 = > 20% reduction)
        size_ratio = 1 - 0.2 * (party_size / 5)
        penalty *= size_ratio
        log += f"* size:{self._percent(size_ratio)}% "

        # 3. Punish based on how long everybody waited.
        # Only applicable if greater than 30 minutes.
        # (less than 30m  = 0.x) / (more than 30m = 1.x)
        if party_age > 30 * 60:
            age_ratio = party_age / (30 * 60)
            penalty *= age_ratio
            log += f"* age:{self._percent(age_ratio)}% "

        # 4. Punished based on how many times the user has flaked in the past N days.
        # The more days that the user flaked on, increases the penalty by 50%. Flakes
        # on the same day are not affected.
        flake_ratio = 0.5 * flake_count + 1
        penalty *= flake_ratio
        log += f"* flake:{self._percent(flake_ratio)}% "

        # 5. Punish less based on how much SSC the user has.
        # Only applicable if the user has less than the starting SSC.
        # Function Requirements: f(STARTING_SSC) = 1, f(0) = 0
        if current_ssc < party.STARTING_SSC:
            tax_break_ratio = (current_ssc**2) / (party.STARTING_SSC**2)
            penalty *= tax_break_ratio
            log += f"* tax-break:{self._percent(tax_break_ratio)}% "

        # 6. Round up to the nearest integer.
        penalty = math.ceil(penalty)

        log += f"= {penalty} SSC for flaking on a party."
        print(log)
        return penalty

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
        # 1. The base reward for joining a party.
        reward = self.BASE_REWARD
        log = f"[user-{user_id}]: CREDIT base-{self.BASE_REWARD} SSC "

        # 2. Reward people with less SSC, the more games they play in a certain period.
        # (first game = 1.0) / (any more after that = 0.x)
        diminishing_ratio = 1 / ((2 * parties_joined) + 1)
        reward = reward * diminishing_ratio
        log += f"* dim:{self._percent(diminishing_ratio)}% "

        # 3. Reward people less based on how much SSC they have.
        # Only applicable if the user has more than the starting SSC.
        # Function Requirements: f(STARTING_SSC) = 1, f(infinity) = 0
        if current_ssc > party.STARTING_SSC:
            tax_ratio = (party.STARTING_SSC**2) / (current_ssc**2)
            reward *= tax_ratio
            log += f"* tax:{self._percent(tax_ratio)}% "

        # 4. Round up to the nearest integer.
        reward = math.ceil(reward)

        log += f"= {reward} SSC for joining a party."
        print(log)
        return reward

    async def process_party_reward(self, party: Party) -> dict[str, dict[str, int]]:
        """
        Process the reward for each player in the party. Returns a dictionary of user
        IDs and the amount of sail credit they received.
        """
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
                party.created_at,
                party.finished_at,
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

        def round_nearest_day(x, base=(24 * 60 * 60)) -> int:
            return base * round(x / base)

        # Calculate how many times in the FLAKE_WINDOW has the user flaked.
        days_flaked = set()
        history = await db.get_user_sail_credit_log(user_id, self.FLAKE_WINDOW)
        for entry in history:
            if entry["new_sail_credit"] - entry["prev_sail_credit"] < 0:
                days_flaked.add(round_nearest_day(entry["timestamp"]))

        # Calculate the penalty for flaking.
        penalty = await self.debit(
            user_id,
            user["sail_credit"],
            len(days_flaked),
            party.finished_at - party.created_at,
            party.size,
        )

        await db.change_and_log_sail_credit(
            user_id,
            party.size,
            party.created_at,
            party.finished_at,
            user["sail_credit"],
            user["sail_credit"] + penalty,
        )
        return {
            "old": user["sail_credit"],
            "new": user["sail_credit"] + penalty,
        }

    def _percent(self, x: float) -> float:
        return round(x * 100, 3)
