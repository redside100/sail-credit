import time
from dataclasses import dataclass
from typing import Dict, List, Optional

from apscheduler.schedulers.asyncio import AsyncIOScheduler

import db
from vct.scraper import VLRMatch, scrape_all_match_data, scrape_event_matches, scrape_match_odds

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
        # Local cache of matches (populated on-demand and from DB)
        self.matches: Dict[int, VLRMatch] = {}

    async def start(self):
        """Initialize the service: load matches from DB and start polling for active bets."""
        await self._load_matches_from_db()
        self.scheduler.add_job(
            self._poll_active_bets,
            "interval",
            seconds=POLL_INTERVAL_SECONDS,
            id="vct_poll_active",
            replace_existing=True,
        )
        self.scheduler.start()
        print("VCT Betting Service started!")

    async def _load_matches_from_db(self):
        """Load cached match data from the database."""
        db_matches = await db.get_vct_matches()
        for m in db_matches:
            self.matches[m["match_id"]] = VLRMatch(
                match_id=m["match_id"],
                team1_name=m["team1_name"],
                team2_name=m["team2_name"],
                team1_odds=m["team1_odds"],
                team2_odds=m["team2_odds"],
                scheduled_time=m["scheduled_time"],
                status=m["status"],
                winner=m["winner"],
                team1_score=m["team1_score"],
                team2_score=m["team2_score"],
                event_name=m["event_name"] or "",
                match_url=m["match_url"] or "",
            )

    async def fetch_matches(self) -> List[VLRMatch]:
        """On-demand scrape of all VCT matches. Called when a user runs /vct matches."""
        try:
            scraped_matches = await scrape_all_match_data()
            now = int(time.time())

            for scraped in scraped_matches:
                await self._upsert_match(scraped, now)

            return list(self.matches.values())
        except Exception as e:
            print(f"VCT fetch_matches error: {e}")
            # Fall back to cached data
            return list(self.matches.values())

    async def _upsert_match(self, scraped: VLRMatch, now: int):
        """Update a match in DB and local cache."""
        await db.upsert_vct_match(
            match_id=scraped.match_id,
            team1_name=scraped.team1_name,
            team2_name=scraped.team2_name,
            team1_odds=scraped.team1_odds,
            team2_odds=scraped.team2_odds,
            scheduled_time=scraped.scheduled_time,
            status=scraped.status,
            winner=scraped.winner,
            team1_score=scraped.team1_score,
            team2_score=scraped.team2_score,
            event_name=scraped.event_name,
            match_url=scraped.match_url,
            last_updated=now,
        )
        self.matches[scraped.match_id] = scraped

    async def _poll_active_bets(self):
        """Only poll VLR.gg for matches that have pending bets, to check for results."""
        try:
            matches_with_bets = await db.get_matches_with_pending_bets()
            if not matches_with_bets:
                return

            match_ids = {row["match_id"] for row in matches_with_bets}

            # Scrape the event page to get current status/results
            scraped_matches = await scrape_event_matches()
            now = int(time.time())

            for scraped in scraped_matches:
                if scraped.match_id not in match_ids:
                    continue

                existing = self.matches.get(scraped.match_id)
                await self._upsert_match(scraped, now)

                # If a match just completed, resolve bets
                if (
                    scraped.status == "completed"
                    and scraped.winner
                    and (not existing or existing.status != "completed")
                ):
                    await self._resolve_match_bets(scraped)

            resolved_count = len(match_ids)
            print(f"VCT poll: checked {resolved_count} match(es) with active bets")
        except Exception as e:
            print(f"VCT poll error: {e}")

    async def _resolve_match_bets(self, match: VLRMatch):
        """Resolve all pending bets for a completed match."""
        pending_bets = await db.get_pending_vct_bets(match.match_id)
        now = int(time.time())

        for bet_row in pending_bets:
            discord_id = bet_row["discord_id"]
            team_pick = bet_row["team_pick"]
            amount = bet_row["amount"]
            potential_payout = bet_row["potential_payout"]

            user = await db.get_user(discord_id)
            if not user:
                continue

            current_ssc = user["sail_credit"]

            if team_pick == match.winner:
                # Winner! Credit the payout
                payout = int(potential_payout)
                new_ssc = current_ssc + payout
                await db.change_and_log_sail_credit(
                    discord_id, -1, -1, -1, current_ssc, new_ssc, "VCT_CREDIT"
                )
                await db.resolve_vct_bet(bet_row["id"], "won", now)
            else:
                # Loser - bet was already deducted at placement time
                await db.resolve_vct_bet(bet_row["id"], "lost", now)

        if pending_bets:
            winner_name = (
                match.team1_name if match.winner == "team1" else match.team2_name
            )
            print(
                f"VCT: Resolved {len(pending_bets)} bets for match {match.match_id} "
                f"({match.team1_name} vs {match.team2_name}) — Winner: {winner_name}"
            )

    def get_upcoming_matches(self) -> List[VLRMatch]:
        """Get all upcoming/live matches that can be bet on."""
        return [
            m
            for m in self.matches.values()
            if m.status in ("upcoming", "live")
            and m.team1_odds is not None
            and m.team2_odds is not None
        ]

    def get_all_matches(self) -> List[VLRMatch]:
        """Get all tracked matches from cache."""
        return list(self.matches.values())

    def get_match(self, match_id: int) -> Optional[VLRMatch]:
        """Get a specific match by ID."""
        return self.matches.get(match_id)

    async def place_bet(
        self,
        discord_id: int,
        match_id: int,
        team_pick: str,
        amount: int,
    ) -> Optional[VCTBet]:
        """
        Place a bet on a VCT match. Returns the bet if successful.
        The caller is responsible for checking the user has enough SSC.
        """
        match = self.matches.get(match_id)
        if not match:
            return None

        if match.status not in ("upcoming", "live"):
            return None

        if team_pick not in ("team1", "team2"):
            return None

        if amount < MIN_BET:
            return None

        # Get current odds
        odds = match.team1_odds if team_pick == "team1" else match.team2_odds
        if odds is None:
            return None

        potential_payout = round(amount * odds, 2)
        now = int(time.time())

        # Deduct SSC
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

        # Create the bet
        bet_id = await db.create_vct_bet(
            discord_id=discord_id,
            match_id=match_id,
            team_pick=team_pick,
            amount=amount,
            odds_at_bet=odds,
            potential_payout=potential_payout,
            placed_at=now,
        )

        return VCTBet(
            id=bet_id,
            discord_id=discord_id,
            match_id=match_id,
            team_pick=team_pick,
            amount=amount,
            odds_at_bet=odds,
            potential_payout=potential_payout,
            status="pending",
            placed_at=now,
        )

    async def refresh_odds(self, match_id: int) -> Optional[VLRMatch]:
        """Force-refresh odds for a specific match."""
        match = self.matches.get(match_id)
        if not match:
            return None

        team1_odds, team2_odds = await scrape_match_odds(
            match.match_id, match.match_url
        )
        if team1_odds is not None:
            match.team1_odds = team1_odds
        if team2_odds is not None:
            match.team2_odds = team2_odds

        now = int(time.time())
        await db.upsert_vct_match(
            match_id=match.match_id,
            team1_name=match.team1_name,
            team2_name=match.team2_name,
            team1_odds=match.team1_odds,
            team2_odds=match.team2_odds,
            scheduled_time=match.scheduled_time,
            status=match.status,
            winner=match.winner,
            team1_score=match.team1_score,
            team2_score=match.team2_score,
            event_name=match.event_name,
            match_url=match.match_url,
            last_updated=now,
        )

        return match
