from typing import TYPE_CHECKING, List, Optional

import discord

from util import create_embed, divide_chunks, user_interaction_callback

if TYPE_CHECKING:
    from vct.betting import VCTBettingService
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


def create_matches_embed(
    matches: List["VLRMatch"], page: int = 0, per_page: int = 5
) -> discord.Embed:
    """Create an embed showing VCT matches with odds."""
    bettable = [m for m in matches if m.status in ("upcoming", "live")]
    completed = [m for m in matches if m.status == "completed"]

    all_matches = bettable + completed

    if not all_matches:
        return create_embed(
            title="🏆 VCT Champions 2026 — Matches",
            message="No matches found! Try again later.",
        )

    start = page * per_page
    end = start + per_page
    page_matches = all_matches[start:end]

    lines = []
    for match in page_matches:
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

    total_pages = (len(all_matches) + per_page - 1) // per_page
    footer = f"\nPage {page + 1}/{total_pages}" if total_pages > 1 else ""

    return create_embed(
        title="🏆 VCT Champions 2026 — Matches",
        message="\n".join(lines) + footer,
    )


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
    opponent = _team_display(match, "team2" if team_pick == "team1" else "team1")

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


def create_user_bets_embed(bets: list, matches: dict, page: int = 0) -> discord.Embed:
    """Create an embed showing a user's VCT bets."""
    if not bets:
        return create_embed(
            title="🎰 Your VCT Bets",
            message="You haven't placed any VCT bets yet!",
        )

    per_page = 8
    start = page * per_page
    end = start + per_page
    page_bets = bets[start:end]

    lines = []
    for bet in page_bets:
        match = matches.get(bet["match_id"])
        if not match:
            continue

        team_name = match["team1_name"] if bet["team_pick"] == "team1" else match["team2_name"]

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
            f"{status_emoji} **{match['team1_name']}** vs **{match['team2_name']}**\n"
            f"  Pick: **{team_name}** | {bet['amount']} SSC @ {bet['odds_at_bet']:.2f}{payout_text}"
        )

    total_pages = (len(bets) + per_page - 1) // per_page
    footer = f"\nPage {page + 1}/{total_pages}" if total_pages > 1 else ""

    return create_embed(
        title="🎰 Your VCT Bets",
        message="\n".join(lines) + footer,
    )


class MatchListView(discord.ui.View):
    """Paginated view for match listings."""

    def __init__(self, user_id: int, matches: List["VLRMatch"], per_page: int = 5):
        super().__init__(timeout=120)
        self.user_id = user_id
        self.matches = matches
        self.per_page = per_page
        self.page = 0
        self.max_page = max(0, (len(matches) + per_page - 1) // per_page - 1)
        self._update_buttons()

    def _update_buttons(self):
        self.prev_button.disabled = self.page <= 0
        self.next_button.disabled = self.page >= self.max_page

    @discord.ui.button(label="◀", style=discord.ButtonStyle.grey)
    async def prev_button(self, interaction: discord.Interaction, button: discord.ui.Button):
        if interaction.user.id != self.user_id:
            await interaction.response.defer()
            return
        self.page = max(0, self.page - 1)
        self._update_buttons()
        embed = create_matches_embed(self.matches, self.page, self.per_page)
        await interaction.response.edit_message(embed=embed, view=self)

    @discord.ui.button(label="▶", style=discord.ButtonStyle.grey)
    async def next_button(self, interaction: discord.Interaction, button: discord.ui.Button):
        if interaction.user.id != self.user_id:
            await interaction.response.defer()
            return
        self.page = min(self.max_page, self.page + 1)
        self._update_buttons()
        embed = create_matches_embed(self.matches, self.page, self.per_page)
        await interaction.response.edit_message(embed=embed, view=self)


class BetUserBetsView(discord.ui.View):
    """Paginated view for user bets."""

    def __init__(self, user_id: int, bets: list, matches: dict):
        super().__init__(timeout=120)
        self.user_id = user_id
        self.bets = bets
        self.matches = matches
        self.per_page = 8
        self.page = 0
        self.max_page = max(0, (len(bets) + self.per_page - 1) // self.per_page - 1)
        self._update_buttons()

    def _update_buttons(self):
        self.prev_button.disabled = self.page <= 0
        self.next_button.disabled = self.page >= self.max_page

    @discord.ui.button(label="◀", style=discord.ButtonStyle.grey)
    async def prev_button(self, interaction: discord.Interaction, button: discord.ui.Button):
        if interaction.user.id != self.user_id:
            await interaction.response.defer()
            return
        self.page = max(0, self.page - 1)
        self._update_buttons()
        embed = create_user_bets_embed(self.bets, self.matches, self.page)
        await interaction.response.edit_message(embed=embed, view=self)

    @discord.ui.button(label="▶", style=discord.ButtonStyle.grey)
    async def next_button(self, interaction: discord.Interaction, button: discord.ui.Button):
        if interaction.user.id != self.user_id:
            await interaction.response.defer()
            return
        self.page = min(self.max_page, self.page + 1)
        self._update_buttons()
        embed = create_user_bets_embed(self.bets, self.matches, self.page)
        await interaction.response.edit_message(embed=embed, view=self)
