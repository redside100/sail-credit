from party import Party


class SailBank:
    """
    Welcome all.

    In calm currents flow,
    Sail Bank charts wealth's steady course—
    Dreams in safe harbors.
    """

    def process(flake: bool):
        """
        Handles the process of calculating sail credit for a user based on whether they
        flaked on a party or not.
        """

        pass

    def debit(self, party: Party, user_id: int):
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
        return -3

    def credit(self, user_id: int):
        """
        Method for calculating how much sail credit to give to a user for not flaking
        on a party.

        Input Parameters:
        - The user's current sail credit.
            - RATIONALE: The more SSC a user has already, the less they gain.
        - The number of parties the user has participated in the past 24 hours.
            - RATIONALE: Subsequent parties in a day should not be as rewarding. This
            rewards consistency instead of just joining a bunch of parties in a day.
        """
        return +3
