import time
from dataclasses import dataclass
from typing import List, Optional

from apscheduler.schedulers.asyncio import AsyncIOScheduler

import db
from vct.scraper import VLRMatch, scrape_all_match_data, scrape_event_matches, scrape_match_page

# How often to poll VLR.gg for matches that have active bets (in seconds)
POLL_INTERVAL_SECONDS = 120
# Minimum bet amount
MIN_BET = 10


@dataclass
class VCTBet:
    id: int
    discord_id: int
    match_id: int
    team_pick: str  # "team1" or "team2"
    amount: int
    odds_at_bet: float
    potential_payout: float
    status: str  # "pending", "won", "lost"
    placed_at: int
    resolved_at: Optional[int] = None


class VCTBettingService:
    def __init__(self):
        self.scheduler = AsyncIOScheduler(timezone="UTC")

    async def start(self):
        """Initialize the service and start polling for active bets."""
        self.scheduler.add_job(
            self._poll_active_bets,
            "interval",
            seconds=POLL_INTERVAL_SECONDS,
            id="vct_poll_active",
            replace_existing=True,
        )
        self.scheduler.start()
        print("VCT Betting Service started!")

    async def fetch_matches(self) -> List[VLRMatch]:
        """On-demand scrape of all VCT matches. Called when a user runs /vct matches."""
        try:
            return await scrape_all_match_data()
        except Exception as e:
            print(f"VCT fetch_matches error: {e}")
            return []

    async def get_match(self, match_id: int) -> Optional[VLRMatch]:
        """Scrape a single match page for current data."""
        try:
            return await scrape_match_page(match_id)
        except Exception as e:
            print(f"VCT get_match error: {e}")
            return None

    async def _poll_active_bets(self):
        """Only poll VLR.gg for matches that have pending bets, to check for results."""
        try:
            matches_with_bets = await db.get_matches_with_pending_bets()
            if not matches_with_bets:
                return

            match_ids = {row["match_id"] for row in matches_with_bets}

            # Scrape the event page to get current status/results
            scraped_matches = await scrape_event_matches()

            for scraped in scraped_matches:
                if scraped.match_id not in match_ids:
                    continue

                if scraped.status == "completed" and scraped.winner:
                    await self._resolve_match_bets(scraped)

            print(f"VCT poll: checked {len(match_ids)} match(es) with active bets")
        except Exception as e:
            print(f"VCT poll error: {e}")

    async def _resolve_match_bets(self, match: VLRMatch):
        """Resolve all pending bets for a completed match."""
        pending_bets = await db.get_pending_vct_bets(match.match_id)
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
                    discord_id, -1, -1, -1, current_ssc, new_ssc, "VCT_CREDIT"
                )
                await db.resolve_vct_bet(bet_row["id"], "won", now)
            else:
                await db.resolve_vct_bet(bet_row["id"], "lost", now)

        winner_name = (
            match.team1_name if match.winner == "team1" else match.team2_name
        )
        print(
            f"VCT: Resolved {len(pending_bets)} bets for match {match.match_id} "
            f"({match.team1_name} vs {match.team2_name}) — Winner: {winner_name}"
        )

    async def place_bet(
        self,
        discord_id: int,
        match: VLRMatch,
        team_pick: str,
        amount: int,
    ) -> Optional[VCTBet]:
        """
        Place a bet on a VCT match. Returns the bet if successful.
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
            discord_id, -1, -1, -1, current_ssc, new_ssc, "VCT_DEBIT"
        )

        bet_id = await db.create_vct_bet(
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

        return VCTBet(
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
