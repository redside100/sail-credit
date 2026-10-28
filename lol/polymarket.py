import json
from dataclasses import dataclass, field
from datetime import datetime
from typing import Any, Dict, List, Optional

import aiohttp

POLYMARKET_API_URL = "https://gamma-api.polymarket.com"
# Live order book. Gamma responses are CDN-cached for up to 5 minutes, so prices come from here instead.
POLYMARKET_CLOB_URL = "https://clob.polymarket.com"
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
    # CLOB token IDs for the match winner market, used to fetch live prices
    token_ids: List[str] = field(default_factory=list)
    # CLOB condition ID for the match winner market, used to check for a result
    condition_id: str = ""


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


async def _fetch_midpoints(token_ids: List[str]) -> Dict[str, str]:
    """Fetch live midpoint prices from the CLOB in one request. Tokens with no order book are omitted."""
    if not token_ids:
        return {}
    url = f"{POLYMARKET_CLOB_URL}/midpoints"
    try:
        async with aiohttp.ClientSession() as session:
            async with session.post(
                url,
                json=[{"token_id": t} for t in token_ids],
                timeout=aiohttp.ClientTimeout(total=10),
            ) as resp:
                if resp.status == 200:
                    return await resp.json()
                print(f"Polymarket: got status {resp.status} for {url}")
                return {}
    except Exception as e:
        print(f"Polymarket: error fetching {url}: {e}")
        return {}


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
        token_ids = json.loads(moneyline.get("clobTokenIds") or "[]")
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
        token_ids=token_ids if len(token_ids) == 2 else [],
        condition_id=moneyline.get("conditionId") or "",
    )


async def fetch_winner(match: LoLMatch) -> Optional[str]:
    """
    Check the live order book for the match winner. Returns "team1", "team2", or None if undecided.
    Unlike Gamma this isn't cached, so results show up as soon as Polymarket settles the market.
    """
    if not match.condition_id or not match.token_ids:
        return None
    url = f"{POLYMARKET_CLOB_URL}/markets/{match.condition_id}"
    try:
        async with aiohttp.ClientSession() as session:
            async with session.get(url, timeout=aiohttp.ClientTimeout(total=10)) as resp:
                if resp.status != 200:
                    print(f"Polymarket: got status {resp.status} for {url}")
                    return None
                market = await resp.json()
    except Exception as e:
        print(f"Polymarket: error fetching {url}: {e}")
        return None

    for token in market.get("tokens", []):
        if token.get("winner") is True:
            if token.get("token_id") == match.token_ids[0]:
                return "team1"
            if token.get("token_id") == match.token_ids[1]:
                return "team2"
    return None


async def refresh_odds(matches: List[LoLMatch]) -> None:
    """
    Overwrite odds on open matches with live order book prices.
    The two outcomes are complementary, so team2's price is 1 - team1's.
    Matches whose order book can't be read keep their Gamma odds.
    """
    open_matches = [
        m for m in matches if m.status in ("upcoming", "live") and m.token_ids
    ]
    midpoints = await _fetch_midpoints([m.token_ids[0] for m in open_matches])
    for match in open_matches:
        try:
            price = float(midpoints[match.token_ids[0]])
        except (KeyError, TypeError, ValueError):
            continue
        match.team1_odds = _price_to_odds(str(price))
        match.team2_odds = _price_to_odds(str(1 - price))


async def fetch_worlds_matches() -> List[LoLMatch]:
    """Fetch all LoL Worlds 2026 matches that have a match winner market, with live odds."""
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

    await refresh_odds(matches)
    return matches


async def fetch_match(match_id: int) -> Optional[LoLMatch]:
    """Fetch a single match by its Polymarket event ID, with live odds."""
    event = await _fetch_json(f"/events/{match_id}")
    if not event:
        return None
    # Only allow Worlds matches, not any Polymarket event ID
    if not any(tag.get("slug") == WORLDS_TAG_SLUG for tag in event.get("tags", [])):
        return None
    match = _parse_event(event)
    if match:
        await refresh_odds([match])
    return match
