import math
import time
from typing import List
from uuid import UUID
import discord

import db
from party import Party, PartyMember, PartyService, PartyStatus
from util import create_embed, disable_buttons_and_stop_view


class ReportSelectView(discord.ui.View):
    def __init__(self, party: Party, reporter_id: int):
        self.party = party
        self.reporter_id = reporter_id
        super().__init__(timeout=60)  # 1m

        self.select = discord.ui.Select(placeholder="Select a user...")
        self.select.callback = self.select_user
        self.select.options = [
            discord.SelectOption(label=member.name, value=member.user_id)
            for member in self.party.members
        ]

        self.add_item(self.select)

    async def select_user(self, interaction: discord.Interaction):
        selected_id = self.select.values[0]
        view = ReportView(self.party)
        await interaction.response.send_message(
            content=f" <@{selected_id}> has been reported by <@{self.reporter_id}>.",
            embed=create_embed(view.generate_embed()),
            view=view,
            ephemeral=False,
            allowed_mentions=discord.AllowedMentions(),
        )


class ReportView(discord.ui.View):
    def __init__(self, party: Party):
        self.party = party
        self.convict_votes = []
        self.acquit_votes = []
        super().__init__(timeout=300)  # 5m

    def generate_embed(self) -> str:
        self.votes_needed = math.ceil(self.party.size / 2)
        convict_ratio = f"`{len(self.convict_votes)}` / `{self.votes_needed}`"
        acquit_ratio = f"`{len(self.acquit_votes)}` / `{self.votes_needed}`"
        content = f"{convict_ratio} to convict.\n{acquit_ratio} to acquit."
        return content

    @discord.ui.button(label="Convict", style=discord.ButtonStyle.red)
    async def convict(self, interaction: discord.Interaction, _):
        # Check if the user is in the party.
        party_member_ids = [member.user_id for member in self.party.members]
        if interaction.user.id not in party_member_ids:
            await interaction.response.send_message(
                "You are not in the party.", ephemeral=True
            )
            return

        # Check if the user has already voted.
        if interaction.user.id in self.convict_votes:
            await interaction.response.send_message(
                "You have already voted to convict.", ephemeral=True
            )
            return

        # Check if the user has already voted to acquit, and remove if so.
        if interaction.user.id in self.acquit_votes:
            self.acquit_votes.remove(interaction.user.id)

        # Record the vote and re-generate the embed.
        self.convict_votes.append(interaction.user.id)
        await interaction.response.defer()
        await interaction.edit_original_response(
            embed=create_embed(self.generate_embed())
        )

    @discord.ui.button(label="Acquit", style=discord.ButtonStyle.green)
    async def aquit(self, interaction: discord.Interaction, _):
        # Check if the user is in the party.
        party_member_ids = [member.user_id for member in self.party.members]
        if interaction.user.id not in party_member_ids:
            await interaction.response.send_message(
                "You are not in the party.", ephemeral=True
            )
            return

        # Check if the user has already voted.
        if interaction.user.id in self.acquit_votes:
            await interaction.response.send_message(
                "You have already voted to convict.", ephemeral=True
            )
            return

        # Check if the user has already voted to convict, and remove if so.
        if interaction.user.id in self.convict_votes:
            self.convict_votes.remove(interaction.user.id)

        # Record the vote and re-generate the embed.
        self.acquit_votes.append(interaction.user.id)
        await interaction.response.defer()
        await interaction.edit_original_response(
            embed=create_embed(self.generate_embed())
        )


class PostPartyView(discord.ui.View):
    def __init__(self, party: Party):
        self.party = party
        super().__init__(timeout=300)  # 5m

    async def interaction_check(self, interaction: discord.Interaction):
        # Only allow party members to interact with this view.
        if interaction.user.id not in [member.user_id for member in self.party.members]:
            return False
        return True

    @discord.ui.button(label="Report", style=discord.ButtonStyle.red)
    async def report(self, interaction: discord.Interaction, _):
        await interaction.response.send_message(
            content="Who do you want to report?",
            view=ReportSelectView(self.party, interaction.user.id),
            ephemeral=True,
        )


class PartyView(discord.ui.View):
    def __init__(self, party: Party, party_service: PartyService):
        self.party: Party = party
        self.party_service = party_service
        super().__init__(timeout=60 * 60)  # 1 hr

    # When this view is inactive, remove the party.
    async def on_timeout(self):
        self.party_service.remove_party(self.party.uuid)

    @discord.ui.button(label="Start", style=discord.ButtonStyle.green)
    async def start(self, interaction: discord.Interaction, _):

        if not interaction.user.id == self.party.owner_id:
            await interaction.response.send_message(
                "Only the party leader can use this button!", ephemeral=True
            )
            return

        await interaction.response.defer()

        # Notify all party members.
        party_mentions = [f"<@{member.user_id}>" for member in self.party.members]

        # Force reportable = true for development
        # TODO: uncomment
        reportable = True
        # reportable = len(self.party.members) > 1

        original_message = await interaction.original_response()
        report_msg = (
            "For the next 5 minutes, any party member can click the **Report** button to report a flaker."
            if reportable
            else "Since this party has less than 2 members, there is no option to report flakers."
        )
        await original_message.reply(
            content="".join(party_mentions),
            embed=create_embed(
                f"<@{self.party.owner_id}> started the party for <@&{self.party.role.id}>!\n\n{report_msg}"
            ),
            view=PostPartyView(self.party) if reportable else None,
        )

        # This party has started, so mark it.
        self.party.status = PartyStatus.STARTED

        self.party_service.remove_party(self.party.uuid)

        await disable_buttons_and_stop_view(self, interaction)

    @discord.ui.button(label="Join", style=discord.ButtonStyle.blurple)
    async def join(self, interaction: discord.Interaction, _):

        # Check if the user is already in the party.
        party_member_ids = [member.user_id for member in self.party.members]
        if interaction.user.id in party_member_ids:
            await interaction.response.send_message(
                "You are already in the party.", ephemeral=True
            )
            return

        # Check if the party is full.
        # TODO: In the future, people can still join parties which are full but are
        # waitlisted.
        if len(self.party.members) >= self.party.size:
            await interaction.response.send_message(
                "The party is full.", ephemeral=True
            )
            return

        self.party.members.append(
            PartyMember(user_id=interaction.user.id, name=interaction.user.name)
        )

        await interaction.response.defer()
        await interaction.edit_original_response(
            embed=create_embed(self.party.generate_embed())
        )

    @discord.ui.button(label="Leave", style=discord.ButtonStyle.red)
    async def leave(self, interaction: discord.Interaction, _):

        # Check if the user is in the party.
        party_member_ids = [member.user_id for member in self.party.members]
        if interaction.user.id not in party_member_ids:
            await interaction.response.send_message(
                "You are not in the party.", ephemeral=True
            )
            return

        old_owner = self.party.owner_id
        self.party.leave_party(interaction.user.id)

        await interaction.response.defer()

        # If the party has no members left, it's abandoned.
        if not self.party.members:
            await interaction.edit_original_response(
                embed=create_embed("This party was abandoned since everyone left."),
                content=None,
            )
            await disable_buttons_and_stop_view(self, interaction)
            return

        await interaction.edit_original_response(
            embed=create_embed(self.party.generate_embed()),
            # If the party has a new owner, announce it.
            content=(
                f"<@{self.party.owner_id}> is the new party leader."
                if self.party.owner_id != old_owner
                else None
            ),
        )


"""
General use view for showing multi-page content.
Accepts a list of embeds.
"""


class MessageBook(discord.ui.View):
    def __init__(
        self,
        user_id: int,
        pages: List[discord.Embed],
    ):
        super().__init__(timeout=120)
        self.page_count = len(pages)

        for i, page in enumerate(pages):
            page.set_footer(text=f"Page {i + 1} of {self.page_count}")

        self.pages = pages
        self.user_id = user_id
        self.current_page = 0

    async def interaction_check(self, interaction: discord.Interaction):
        if interaction.user.id != self.user_id:
            return False
        return True

    @discord.ui.button(label="Prev", style=discord.ButtonStyle.blurple)
    async def prev_button(self, interaction: discord.Interaction, _):
        if not interaction.user.id == self.user_id:
            return

        await self.prev_page(interaction)

    @discord.ui.button(label="Next", style=discord.ButtonStyle.blurple)
    async def next_button(self, interaction: discord.Interaction, _):
        if not interaction.user.id == self.user_id:
            return

        await self.next_page(interaction)

    async def next_page(self, interaction: discord.Interaction):
        self.current_page += 1
        if self.current_page > len(self.pages) - 1:
            self.current_page = 0

        await self.update_page(interaction)

    async def prev_page(self, interaction: discord.Interaction):
        self.current_page -= 1
        if self.current_page < 0:
            self.current_page = len(self.pages) - 1

        await self.update_page(interaction)

    async def update_page(self, interaction: discord.Interaction):
        await interaction.response.defer()
        await interaction.edit_original_response(embed=self.pages[self.current_page])
