import time
from dataclasses import dataclass
from datetime import datetime, timezone
from typing import Any, Dict, List, Optional

from apscheduler.schedulers.asyncio import AsyncIOScheduler

import db
from lol.polymarket import (
    LoLMatch,
    fetch_match,
    fetch_winner,
    fetch_worlds_matches,
    refresh_odds,
)

# How often to poll Polymarket to refresh matches/odds and resolve bets (in seconds)
POLL_INTERVAL_SECONDS = 120
# Minimum bet amount
MIN_BET = 10


@dataclass
class LoLBet:
    id: int
    discord_id: int
    match_id: int
    team_pick: str  # "team1" or "team2"
    amount: int
    odds_at_bet: float
    potential_payout: float
    status: str  # "pending", "won", "lost", "refunded"
    placed_at: int
    resolved_at: Optional[int] = None


class LoLBettingService:
    def __init__(self):
        self.scheduler = AsyncIOScheduler(timezone="UTC")
        # All matches from the last poll, keyed by match ID
        self.matches: Dict[int, LoLMatch] = {}

    async def start(self):
        """Initialize the service and start polling. The first poll runs immediately."""
        self.scheduler.add_job(
            self._poll,
            "interval",
            seconds=POLL_INTERVAL_SECONDS,
            id="lol_poll",
            replace_existing=True,
            next_run_time=datetime.now(timezone.utc),
        )
        self.scheduler.start()
        print("LoL Betting Service started!")

    def get_matches(self) -> List[LoLMatch]:
        """All matches from the last poll. Used for display only — bets use get_match()."""
        return list(self.matches.values())

    async def refresh_odds(self):
        """Update in-memory odds from the live order book. One request, so it's cheap to call per command."""
        try:
            await refresh_odds(list(self.matches.values()))
        except Exception as e:
            print(f"LoL refresh_odds error: {e}")

    async def get_match(self, match_id: int) -> Optional[LoLMatch]:
        """Fetch a single match for current data, so bets lock in fresh odds."""
        try:
            return await fetch_match(match_id)
        except Exception as e:
            print(f"LoL get_match error: {e}")
            return None

    async def get_user_pending_bets_for_match(
        self, discord_id: int, match_id: int
    ) -> List[Dict[str, Any]]:
        return await db.get_user_pending_lol_bets_for_match(discord_id, match_id)

    async def _poll(self):
        """Refresh all matches and odds from Polymarket, then resolve any finished bets."""
        try:
            matches = await fetch_worlds_matches()
            if matches:
                self.matches = {m.match_id: m for m in matches}

            matches_with_bets = await db.get_lol_matches_with_pending_bets()
            for row in matches_with_bets:
                match = self.matches.get(row["match_id"]) or await fetch_match(row["match_id"])
                if not match:
                    continue

                # Gamma (the match list) is CDN-cached for up to 5 minutes, so check the
                # live order book for a winner first instead of waiting for Gamma to catch up.
                if not match.winner:
                    winner = await fetch_winner(match)
                    if winner:
                        match.winner = winner
                        match.status = "completed"
                        match.team1_odds = match.team2_odds = None

                if match.status == "completed" and match.winner:
                    await self._resolve_match_bets(match)
                elif match.status == "cancelled":
                    await self._refund_match_bets(match)

            print(
                f"LoL poll: refreshed {len(matches)} match(es), "
                f"checked {len(matches_with_bets)} with active bets"
            )
        except Exception as e:
            print(f"LoL poll error: {e}")

    async def _resolve_match_bets(self, match: LoLMatch):
        """Resolve all pending bets for a completed match."""
        pending_bets = await db.get_pending_lol_bets(match.match_id)
        if not pending_bets:
            return

        now = int(time.time())

        for bet_row in pending_bets:
            discord_id = bet_row["discord_id"]
            team_pick = bet_row["team_pick"]
            potential_payout = bet_row["potential_payout"]

            user = await db.get_user(discord_id)
            if not user:
                continue

            current_ssc = user["sail_credit"]

            if team_pick == match.winner:
                payout = int(potential_payout)
                new_ssc = current_ssc + payout
                await db.change_and_log_sail_credit(
                    discord_id, -1, -1, -1, current_ssc, new_ssc, "LOL_CREDIT"
                )
                await db.resolve_lol_bet(bet_row["id"], "won", now)
            else:
                await db.resolve_lol_bet(bet_row["id"], "lost", now)

        winner_name = (
            match.team1_name if match.winner == "team1" else match.team2_name
        )
        print(
            f"LoL: Resolved {len(pending_bets)} bets for match {match.match_id} "
            f"({match.team1_name} vs {match.team2_name}) — Winner: {winner_name}"
        )

    async def _refund_match_bets(self, match: LoLMatch):
        """Refund all pending bets for a match that was cancelled."""
        pending_bets = await db.get_pending_lol_bets(match.match_id)
        if not pending_bets:
            return

        now = int(time.time())

        for bet_row in pending_bets:
            discord_id = bet_row["discord_id"]

            user = await db.get_user(discord_id)
            if not user:
                continue

            current_ssc = user["sail_credit"]
            new_ssc = current_ssc + bet_row["amount"]
            await db.change_and_log_sail_credit(
                discord_id, -1, -1, -1, current_ssc, new_ssc, "LOL_REFUND"
            )
            await db.resolve_lol_bet(bet_row["id"], "refunded", now)

        print(
            f"LoL: Refunded {len(pending_bets)} bets for cancelled match {match.match_id} "
            f"({match.team1_name} vs {match.team2_name})"
        )

    async def place_bet(
        self,
        discord_id: int,
        match: LoLMatch,
        team_pick: str,
        amount: int,
    ) -> Optional[LoLBet]:
        """
        Place a bet on a LoL match. Returns the bet if successful.
        The caller is responsible for checking the user has enough SSC.
        """
        if match.status not in ("upcoming", "live"):
            return None

        if team_pick not in ("team1", "team2"):
            return None

        if amount < MIN_BET:
            return None

        odds = match.team1_odds if team_pick == "team1" else match.team2_odds
        if odds is None:
            return None

        potential_payout = round(amount * odds, 2)
        now = int(time.time())

        user = await db.get_user(discord_id)
        if not user:
            return None

        current_ssc = user["sail_credit"]
        if current_ssc < amount:
            return None

        new_ssc = current_ssc - amount
        await db.change_and_log_sail_credit(
            discord_id, -1, -1, -1, current_ssc, new_ssc, "LOL_DEBIT"
        )

        bet_id = await db.create_lol_bet(
            discord_id=discord_id,
            match_id=match.match_id,
            team1_name=match.team1_name,
            team2_name=match.team2_name,
            team_pick=team_pick,
            amount=amount,
            odds_at_bet=odds,
            potential_payout=potential_payout,
            placed_at=now,
        )

        return LoLBet(
            id=bet_id,
            discord_id=discord_id,
            match_id=match.match_id,
            team_pick=team_pick,
            amount=amount,
            odds_at_bet=odds,
            potential_payout=potential_payout,
            status="pending",
            placed_at=now,
        )
