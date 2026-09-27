from typing import TYPE_CHECKING, Dict, List, Optional

import discord

from util import create_embed, divide_chunks

if TYPE_CHECKING:
    from vct.scraper import VLRMatch


def _odds_display(odds: Optional[float]) -> str:
    if odds is None:
        return "N/A"
    return f"{odds:.2f}"


def _team_display(match: "VLRMatch", team: str) -> str:
    if team == "team1":
        return match.team1_name
    return match.team2_name


def _status_emoji(status: str) -> str:
    if status == "upcoming":
        return "🔜"
    elif status == "live":
        return "🔴"
    elif status == "completed":
        return "✅"
    return "❓"


def build_matches_pages(
    matches: List["VLRMatch"], per_page: int = 5
) -> List[discord.Embed]:
    """Build a list of embeds for VCT matches, one per page."""
    bettable = [m for m in matches if m.status in ("upcoming", "live")]
    completed = [m for m in matches if m.status == "completed"]
    all_matches = bettable + completed

    if not all_matches:
        return [
            create_embed(
                title="🏆 VCT Champions 2026 — Matches",
                message="No matches found! Try again later.",
            )
        ]

    pages = []
    for chunk in divide_chunks(all_matches, per_page):
        lines = []
        for match in chunk:
            emoji = _status_emoji(match.status)

            if match.status in ("upcoming", "live"):
                odds1 = _odds_display(match.team1_odds)
                odds2 = _odds_display(match.team2_odds)
                lines.append(
                    f"{emoji} **`{match.match_id}`** — "
                    f"**{match.team1_name}** ({odds1}) vs **{match.team2_name}** ({odds2})"
                )
                if match.series_name:
                    lines.append(f"  ↳ {match.series_name}")
            else:
                score = ""
                if match.team1_score is not None and match.team2_score is not None:
                    score = f" ({match.team1_score}-{match.team2_score})"
                winner_name = ""
                if match.winner:
                    winner_name = _team_display(match, match.winner)
                lines.append(
                    f"{emoji} **{match.team1_name}** vs **{match.team2_name}**{score}"
                    + (f" — Winner: **{winner_name}**" if winner_name else "")
                )

        pages.append(
            create_embed(
                title="🏆 VCT Champions 2026 — Matches",
                message="\n".join(lines),
            )
        )

    return pages


def create_bet_confirm_embed(
    match: "VLRMatch",
    team_pick: str,
    amount: int,
    odds: float,
    potential_payout: float,
    new_balance: int,
) -> discord.Embed:
    """Create an embed confirming a bet placement."""
    team_name = _team_display(match, team_pick)

    return create_embed(
        title="🎰 VCT Bet Placed!",
        message=(
            f"**{match.team1_name}** vs **{match.team2_name}**\n\n"
            f"Your pick: **{team_name}** to win\n"
            f"Bet amount: **{amount} SSC**\n"
            f"Locked odds: **{odds:.2f}**\n"
            f"Potential payout: **{int(potential_payout)} SSC**\n\n"
            f"Remaining balance: **{new_balance} SSC**"
        ),
        color=0x61B875,
    )


def build_user_bets_pages(
    bets: list, per_page: int = 8
) -> List[discord.Embed]:
    """Build a list of embeds for a user's VCT bets, one per page."""
    if not bets:
        return [
            create_embed(
                title="🎰 Your VCT Bets",
                message="You haven't placed any VCT bets yet!",
            )
        ]

    pages = []
    for chunk in divide_chunks(bets, per_page):
        lines = []
        for bet in chunk:
            team_name = (
                bet["team1_name"]
                if bet["team_pick"] == "team1"
                else bet["team2_name"]
            )

            status_emoji = {
                "pending": "⏳",
                "won": "💰",
                "lost": "❌",
            }.get(bet["status"], "❓")

            payout_text = ""
            if bet["status"] == "won":
                payout_text = f" → **+{int(bet['potential_payout'])} SSC**"
            elif bet["status"] == "lost":
                payout_text = f" → **-{bet['amount']} SSC**"

            lines.append(
                f"{status_emoji} **{bet['team1_name']}** vs **{bet['team2_name']}**\n"
                f"  Pick: **{team_name}** | {bet['amount']} SSC @ {bet['odds_at_bet']:.2f}{payout_text}"
            )

        pages.append(
            create_embed(
                title="🎰 Your VCT Bets",
                message="\n".join(lines),
            )
        )

    return pages
