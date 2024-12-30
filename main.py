import asyncio
from dataclasses import asdict
import time
from typing import Literal, Optional
from discord import app_commands
import discord
from discord.ext import commands
import db
from party import Party, PartyService

from util import create_ssc_graph_url, divide_chunks, user_command, create_embed
from views import LeaderboardView, PartyView, MessageBook

intents = discord.Intents.default()
bot = commands.Bot(
    command_prefix="/",
    intents=intents,
    case_insensitive=False,
)

party_service: Optional[PartyService] = None


@bot.tree.command(
    name="party-up",
    description="Creates a party, allowing others to let you know they want to join!",
)
@app_commands.describe(
    role="The role of the party you're creating (e.g. @goofy「无畏契约」, @flaccid)",
    name="The name of the party (optional)",
    size="The size of the party (default is 5)",
    description="Any additional information you want to provide about the party.",
)
@user_command()
async def create_party(
    interaction: discord.Interaction,
    role: discord.Role,
    name: Optional[str],
    size: Optional[int],
    description: Optional[str],
):
    created_at = int(time.time())
    party: Party = party_service.create_party(
        user=interaction.user,
        role=role,
        name=name,
        size=size,
        description=description,
        created_at=created_at,
        interaction=interaction,
    )

    content = f"<@{interaction.user.id}> has created a party for <@&{role.id}>!\n"
    if party.description:
        content += f"Description: `{party.description}`\n"

    await interaction.response.send_message(
        content=content,
        embed=create_embed(party.generate_embed()),
        view=PartyView(party, party_service),
        ephemeral=False,
        allowed_mentions=discord.AllowedMentions(),
    )

    # Get the jump URL (message link) for the party for management commands
    message = await interaction.original_response()
    party.jump_url = message.jump_url


@bot.tree.command(
    name="parties", description="List of active parties you're a part of!"
)
@app_commands.describe(leader="If True, only list parties that you're the leader of.")
@user_command()
async def parties(interaction: discord.Interaction, leader: Optional[bool] = False):
    personal_party_list = []
    for party in party_service.parties.values():
        member_ids = {m.user_id for m in party.members}
        if interaction.user.id in member_ids and (
            not leader or interaction.user.id == party.owner_id
        ):
            personal_party_list.append(party)

    party_message = "\n".join(
        [
            f"{'👑 ' if p.owner_id == interaction.user.id else ''}{p.name} {p.jump_url}"
            for p in personal_party_list
        ]
    )
    await interaction.response.send_message(
        embed=create_embed(
            title=f"{interaction.user.display_name}'s Active Parties",
            message=party_message if party_message else "No Parties!",
        )
    )


@bot.tree.command(name="ssc", description="Check your Sail Social Credit (SSC) score!")
@user_command()
async def ssc(interaction: discord.Interaction):
    await interaction.response.send_message(
        embed=create_embed(
            message=f"<@{interaction.user.id}>'s Sail Social Credit: **{interaction.data['user_data']['sail_credit']}**"
        ),
    )


@bot.tree.context_menu(name="Get SSC")
@user_command()
async def get_ssc(interaction: discord.Interaction, user: discord.User):
    user_info = await db.get_user(user.id)
    if not user_info:
        await interaction.response.send_message(
            embed=create_embed(message="This user hasn't used the bot before!"),
            ephemeral=True,
        )
        return

    await interaction.response.send_message(
        embed=create_embed(
            message=f"<@{user.id}>'s Sail Social Credit: **{user_info['sail_credit']}**"
        ),
    )


@bot.tree.command(name="leaderboard", description="Check the SSC leaderboard!")
@user_command()
async def leaderboard(interaction: discord.Interaction):
    pages = []
    users = await db.get_ssc_leaderboard()
    chunks = divide_chunks(users, 10)

    me_page_idx = 0
    for i, chunk in enumerate(chunks):
        page_contents = []
        for j, user in enumerate(chunk):
            rank = i * 10 + j + 1
            page_contents.append(
                f"**#{rank}** <@{user['discord_id']}> ({user['sail_credit']} SSC)"
            )

            if user["discord_id"] == interaction.user.id:
                me_page_idx = i

        pages.append(
            create_embed(title="SSC Leaderboard", message="\n".join(page_contents))
        )

    if not pages:
        await interaction.response.send_message(
            embed=create_embed(title="SSC Leaderboard", message="Nobody!"),
        )
        return

    await interaction.response.send_message(
        embed=pages[0],
        view=LeaderboardView(
            user_id=interaction.user.id, pages=pages, me_page=me_page_idx
        ),
    )


@bot.tree.command(
    name="ssc-graph", description="Check a graph of your SSC over a time period!"
)
@user_command()
async def ssc_graph(
    interaction: discord.Interaction,
    period: Literal["1h", "6h", "12h", "1d", "7d", "30d"],
):
    graph_url = await create_ssc_graph_url(
        interaction.user.id, interaction.user.display_name, period
    )
    await interaction.response.send_message(content=graph_url)


@bot.tree.command(name="search", description="Searches for active parties for a role!")
@app_commands.describe(role="The discord role the party should be for.")
@user_command()
async def search(interaction: discord.Interaction, role: discord.Role):
    party_list = []
    for party in party_service.parties.values():
        if party.role.id == role.id:
            party_list.append(party)

    party_message = "\n".join(
        [
            f"{'👑 ' if p.owner_id == interaction.user.id else ''}{p.name} {p.jump_url}"
            for p in party_list
        ]
    )
    await interaction.response.send_message(
        embed=create_embed(
            title=f"Party search for @{role.name}",
            message=party_message if party_message else "No Parties!",
        )
    )


@bot.event
async def on_ready():
    global party_service
    party_service = PartyService()
    await bot.tree.sync()
    print("Ready!")


# janky function to patch discord.py's bot close to include our async db cleanup
def patch_close():
    original_close_fn = bot.close

    async def new_close(*args, **kwargs):
        await db.cleanup()
        await original_close_fn(*args, **kwargs)

    bot.close = new_close


if __name__ == "__main__":
    asyncio.run(db.init())

    with open("token", "r") as f:
        token = f.read()

    patch_close()
    bot.run(token)
