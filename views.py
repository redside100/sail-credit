import time
from typing import List
from uuid import UUID
import discord

import db
from party import Party, PartyMember, PartyService
from util import create_embed


class PartyView(discord.ui.View):
    def __init__(self, party: Party, party_service: PartyService):
        self.party: Party = party
        self.party_service = party_service
        super().__init__(timeout=60 * 60)  # 1 hr

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
        original_message = await interaction.original_response()
        await original_message.reply(
            content="".join(party_mentions),
            embed=create_embed(
                f"<@{self.party.owner_id}> started the party for <@&{self.party.role.id}>!"
            ),
            view=None,
        )

        # This party has started, so remove it.
        self.party_service.remove_party(self.party.uuid)
        self.stop()

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

        self.party.members.append(PartyMember(user_id=interaction.user.id))

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
                view=None,
            )
            self.stop()
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
