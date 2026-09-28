import re
import time
from dataclasses import dataclass, field
from typing import Dict, List, Optional, Tuple

import aiohttp
from bs4 import BeautifulSoup

VLR_BASE_URL = "https://www.vlr.gg"
VCT_CHAMPIONS_EVENT_ID = 2766
USER_AGENT = "Mozilla/5.0 (Macintosh; Intel Mac OS X 10_15_7) AppleWebKit/537.36 (KHTML, like Gecko) Chrome/120.0.0.0 Safari/537.36"


@dataclass
class VLRMatch:
    match_id: int
    team1_name: str
    team2_name: str
    team1_short: str = ""
    team2_short: str = ""
    team1_odds: Optional[float] = None
    team2_odds: Optional[float] = None
    scheduled_time: Optional[int] = None
    status: str = "upcoming"  # upcoming, live, completed, cancelled
    winner: Optional[str] = None  # "team1" or "team2"
    team1_score: Optional[int] = None
    team2_score: Optional[int] = None
    event_name: str = ""
    series_name: str = ""
    match_url: str = ""


async def _fetch_page(url: str) -> Optional[str]:
    """Fetch a page from VLR.gg with proper headers."""
    headers = {"User-Agent": USER_AGENT}
    try:
        async with aiohttp.ClientSession() as session:
            async with session.get(url, headers=headers, timeout=aiohttp.ClientTimeout(total=15)) as resp:
                if resp.status == 200:
                    return await resp.text()
                print(f"VLR scraper: got status {resp.status} for {url}")
                return None
    except Exception as e:
        print(f"VLR scraper: error fetching {url}: {e}")
        return None


def _parse_match_id_from_href(href: str) -> Optional[int]:
    """Extract match ID from a VLR.gg match URL path like /753444/team-vs-team-..."""
    match = re.match(r"^/(\d+)/", href)
    if match:
        return int(match.group(1))
    return None


async def scrape_event_matches() -> List[VLRMatch]:
    """Scrape all matches from the VCT Champions event page."""
    url = f"{VLR_BASE_URL}/event/matches/{VCT_CHAMPIONS_EVENT_ID}/valorant-champions-2026/?series_id=all"
    html = await _fetch_page(url)
    if not html:
        return []

    soup = BeautifulSoup(html, "html.parser")
    matches = []

    for item in soup.select("a.match-item"):
        href = item.get("href", "")
        match_id = _parse_match_id_from_href(href)
        if not match_id:
            continue

        # Team names
        team_divs = item.select(".match-item-vs-team")
        if len(team_divs) < 2:
            continue

        team1_el = team_divs[0].select_one(".text-of")
        team2_el = team_divs[1].select_one(".text-of")
        if not team1_el or not team2_el:
            continue

        team1_name = team1_el.get_text(strip=True)
        team2_name = team2_el.get_text(strip=True)

        # Skip TBD matches
        if team1_name == "TBD" or team2_name == "TBD":
            continue

        # Scores
        team1_score_el = team_divs[0].select_one(".match-item-vs-team-score")
        team2_score_el = team_divs[1].select_one(".match-item-vs-team-score")
        team1_score = None
        team2_score = None
        if team1_score_el:
            try:
                team1_score = int(team1_score_el.get_text(strip=True))
            except ValueError:
                pass
        if team2_score_el:
            try:
                team2_score = int(team2_score_el.get_text(strip=True))
            except ValueError:
                pass

        # Status
        status = "upcoming"
        winner = None
        status_el = item.select_one(".ml-status")
        if status_el:
            status_text = status_el.get_text(strip=True).lower()
            if "completed" in status_text:
                status = "completed"
            elif "live" in status_text:
                status = "live"

        # Winner detection
        if status == "completed":
            winner_div = item.select_one(".match-item-vs-team.mod-winner")
            if winner_div:
                winner_name_el = winner_div.select_one(".text-of")
                if winner_name_el:
                    winner_name = winner_name_el.get_text(strip=True)
                    if winner_name == team1_name:
                        winner = "team1"
                    elif winner_name == team2_name:
                        winner = "team2"

        # Series/stage info
        series_el = item.select_one(".match-item-event-series")
        series_name = series_el.get_text(strip=True) if series_el else ""

        vlr_match = VLRMatch(
            match_id=match_id,
            team1_name=team1_name,
            team2_name=team2_name,
            team1_score=team1_score,
            team2_score=team2_score,
            status=status,
            winner=winner,
            event_name="Valorant Champions 2026",
            series_name=series_name,
            match_url=f"{VLR_BASE_URL}{href}",
        )
        matches.append(vlr_match)

    return matches


def _find_ggbet_item(bet_items):
    """Find the GGBet sportsbook entry from the list of bet items on a VLR.gg match page."""
    for item in bet_items:
        img = item.select_one("img[src*='ggbet']")
        if img:
            return item
    # Fallback: GGBet is typically the first sportsbook listed
    return bet_items[0] if bet_items else None


async def scrape_match_odds(match_id: int, match_url: str = "") -> Tuple[Optional[float], Optional[float]]:
    """Scrape betting odds from an individual match page. Returns (team1_odds, team2_odds)."""
    if not match_url:
        # Build URL from match_id; we need to fetch the event page first
        # For simplicity, try a direct approach
        match_url = f"{VLR_BASE_URL}/{match_id}"

    html = await _fetch_page(match_url)
    if not html:
        return None, None

    soup = BeautifulSoup(html, "html.parser")

    # Look for the first betting odds section (from the first sportsbook listed)
    bet_items = soup.select("a.match-bet-item")
    if not bet_items:
        # Fallback: check the botd-ggn-team-odds in the sidebar ad
        odds_els = soup.select(".botd-ggn-team-odds")
        if len(odds_els) >= 2:
            try:
                team1_odds = float(odds_els[0].get_text(strip=True))
                team2_odds = float(odds_els[1].get_text(strip=True))
                return team1_odds, team2_odds
            except (ValueError, IndexError):
                pass
        return None, None

    # Use GGBet odds (first sportsbook listed on VLR.gg)
    ggbet_item = _find_ggbet_item(bet_items)
    if not ggbet_item:
        return None, None

    team1_odds = None
    team2_odds = None
    odds_1_el = ggbet_item.select_one(".match-bet-item-odds.mod-1")
    odds_2_el = ggbet_item.select_one(".match-bet-item-odds.mod-2")

    if odds_1_el:
        try:
            team1_odds = float(odds_1_el.get_text(strip=True))
        except ValueError:
            pass
    if odds_2_el:
        try:
            team2_odds = float(odds_2_el.get_text(strip=True))
        except ValueError:
            pass

    return team1_odds, team2_odds


async def scrape_match_page(match_id: int) -> Optional[VLRMatch]:
    """Scrape a single match page for team names, odds, and status."""
    url = f"{VLR_BASE_URL}/{match_id}"
    html = await _fetch_page(url)
    if not html:
        return None

    soup = BeautifulSoup(html, "html.parser")

    header = soup.select_one(".match-header-vs")
    if not header:
        return None

    team1_el = header.select_one(".match-header-link.mod-1 .wf-title-med")
    team2_el = header.select_one(".match-header-link.mod-2 .wf-title-med")
    if not team1_el or not team2_el:
        return None

    team1_name = team1_el.get_text(strip=True)
    team2_name = team2_el.get_text(strip=True)

    # Status
    status = "upcoming"
    notes = header.select(".match-header-vs-note")
    for note in notes:
        note_text = note.get_text(strip=True).lower()
        if "final" in note_text:
            status = "completed"
        elif "live" in note_text:
            status = "live"

    # Odds (GGBet only)
    team1_odds = None
    team2_odds = None
    bet_items = soup.select("a.match-bet-item")
    if bet_items:
        ggbet_item = _find_ggbet_item(bet_items)
        if ggbet_item:
            o1 = ggbet_item.select_one(".match-bet-item-odds.mod-1")
            o2 = ggbet_item.select_one(".match-bet-item-odds.mod-2")
            if o1:
                try:
                    team1_odds = float(o1.get_text(strip=True))
                except ValueError:
                    pass
            if o2:
                try:
                    team2_odds = float(o2.get_text(strip=True))
                except ValueError:
                    pass

    return VLRMatch(
        match_id=match_id,
        team1_name=team1_name,
        team2_name=team2_name,
        team1_odds=team1_odds,
        team2_odds=team2_odds,
        status=status,
        match_url=url,
    )


async def scrape_all_match_data() -> List[VLRMatch]:
    """
    Scrape all VCT Champions matches from the event page,
    then fetch odds for upcoming matches from individual pages.
    """
    matches = await scrape_event_matches()

    # Fetch odds for upcoming/live matches
    for match in matches:
        if match.status in ("upcoming", "live"):
            team1_odds, team2_odds = await scrape_match_odds(
                match.match_id, match.match_url
            )
            match.team1_odds = team1_odds
            match.team2_odds = team2_odds

    return matches
