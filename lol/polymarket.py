import json
from dataclasses import dataclass
from datetime import datetime
from typing import Any, Dict, List, Optional

import aiohttp

POLYMARKET_API_URL = "https://gamma-api.polymarket.com"
POLYMARKET_BASE_URL = "https://polymarket.com"
WORLDS_TAG_SLUG = "lol-worlds-2026"
PAGE_LIMIT = 100


@dataclass
class LoLMatch:
    match_id: int  # Polymarket event ID
    team1_name: str
    team2_name: str
    team1_odds: Optional[float] = None
    team2_odds: Optional[float] = None
    scheduled_time: Optional[int] = None
    status: str = "upcoming"  # upcoming, live, completed, cancelled
    winner: Optional[str] = None  # "team1" or "team2"
    team1_score: Optional[int] = None
    team2_score: Optional[int] = None
    series_name: str = ""
    match_url: str = ""


async def _fetch_json(path: str, params: Optional[Dict[str, Any]] = None) -> Optional[Any]:
    """Fetch JSON from the Polymarket Gamma API."""
    url = f"{POLYMARKET_API_URL}{path}"
    try:
        async with aiohttp.ClientSession() as session:
            async with session.get(url, params=params, timeout=aiohttp.ClientTimeout(total=15)) as resp:
                if resp.status == 200:
                    return await resp.json()
                print(f"Polymarket: got status {resp.status} for {url}")
                return None
    except Exception as e:
        print(f"Polymarket: error fetching {url}: {e}")
        return None


def _price_to_odds(price: str) -> Optional[float]:
    """Convert a Polymarket price (implied probability) into decimal odds."""
    try:
        p = float(price)
    except (TypeError, ValueError):
        return None
    if p <= 0 or p >= 1:
        return None
    return round(1 / p, 2)


def _parse_series_score(score: str) -> tuple:
    """Parse a score string like '000-000|2-3|Bo5' into (team1_score, team2_score)."""
    parts = (score or "").split("|")
    if len(parts) < 2:
        return None, None
    try:
        s1, s2 = parts[1].split("-")
        return int(s1), int(s2)
    except ValueError:
        return None, None


def _parse_event(event: Dict[str, Any]) -> Optional[LoLMatch]:
    """Build a LoLMatch from a Polymarket event. Returns None for non-match events (props, futures)."""
    moneyline = next(
        (m for m in event.get("markets", []) if m.get("sportsMarketType") == "moneyline"),
        None,
    )
    if not moneyline:
        return None

    try:
        outcomes = json.loads(moneyline.get("outcomes") or "[]")
        prices = json.loads(moneyline.get("outcomePrices") or "[]")
    except json.JSONDecodeError:
        return None
    if len(outcomes) != 2 or len(prices) != 2:
        return None

    scheduled_time = None
    if event.get("startTime"):
        try:
            scheduled_time = int(
                datetime.fromisoformat(event["startTime"].replace("Z", "+00:00")).timestamp()
            )
        except ValueError:
            pass

    team1_score, team2_score = _parse_series_score(event.get("score", ""))

    # Status & winner — the match winner market resolves to price "1" for the winning team
    status = "upcoming"
    winner = None
    team1_odds = _price_to_odds(prices[0])
    team2_odds = _price_to_odds(prices[1])

    if moneyline.get("closed") and moneyline.get("umaResolutionStatus") == "resolved":
        if prices[0] == "1":
            winner = "team1"
            status = "completed"
        elif prices[1] == "1":
            winner = "team2"
            status = "completed"
        else:
            # Resolved without a winner (e.g. 50/50 on a cancelled match)
            status = "cancelled"
        team1_odds = team2_odds = None
    elif event.get("ended") or moneyline.get("closed"):
        # Match is over but the market hasn't resolved yet
        status = "completed"
        team1_odds = team2_odds = None
    elif event.get("live"):
        status = "live"

    stage = (event.get("eventMetadata") or {}).get("tournament", "")

    return LoLMatch(
        match_id=int(event["id"]),
        team1_name=outcomes[0],
        team2_name=outcomes[1],
        team1_odds=team1_odds,
        team2_odds=team2_odds,
        scheduled_time=scheduled_time,
        status=status,
        winner=winner,
        team1_score=team1_score,
        team2_score=team2_score,
        series_name=f"Worlds {stage}" if stage else "Worlds",
        match_url=f"{POLYMARKET_BASE_URL}/event/{event.get('slug', '')}",
    )


async def fetch_worlds_matches() -> List[LoLMatch]:
    """Fetch all LoL Worlds 2026 matches that have a match winner market."""
    matches = []
    offset = 0
    while True:
        events = await _fetch_json(
            "/events",
            {"tag_slug": WORLDS_TAG_SLUG, "limit": PAGE_LIMIT, "offset": offset},
        )
        if not events:
            break

        for event in events:
            match = _parse_event(event)
            if match:
                matches.append(match)

        if len(events) < PAGE_LIMIT:
            break
        offset += PAGE_LIMIT

    return matches


async def fetch_match(match_id: int) -> Optional[LoLMatch]:
    """Fetch a single match by its Polymarket event ID."""
    event = await _fetch_json(f"/events/{match_id}")
    if not event:
        return None
    # Only allow Worlds matches, not any Polymarket event ID
    if not any(tag.get("slug") == WORLDS_TAG_SLUG for tag in event.get("tags", [])):
        return None
    return _parse_event(event)
