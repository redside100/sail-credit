import asyncio
import os
import time
from typing import Literal, Optional
from discord import app_commands
import discord
from discord.ext import commands
import db
from party import Party, PartyService

from util import (
    create_ssc_graph_url,
    divide_chunks,
    get_scheduled_datetime_from_string,
    user_command,
    create_embed,
)
from views import LeaderboardView, MessageBook, PartyView

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
    max_size="The max size of the party (default is 5)",
    description="Any additional information you want to provide about the party.",
    start_time="The initial time for the party to start. Format is HH:MM [AM/PM] [EST/PST]. Default timezone is EST.",
)
@user_command()
async def create_party(
    interaction: discord.Interaction,
    role: discord.Role,
    name: Optional[str],
    max_size: Optional[int],
    description: Optional[str],
    start_time: Optional[str],
):
    created_at = int(time.time())

    parsed_start_time = None
    if start_time:
        parsed_start_time, time_parsing_error = get_scheduled_datetime_from_string(
            start_time
        )

        if time_parsing_error:
            await interaction.response.send_message(
                embed=create_embed(
                    message=f"There was a problem while parsing the start time: `{start_time}`.\n\n{time_parsing_error}",
                ),
                ephemeral=True,
            )
            return

    role_image_url = await db.get_role_image_url(role.id)
    party: Party = party_service.create_party(
        user=interaction.user,
        user_ssc=interaction.data["user_data"]["sail_credit"],
        role=role,
        name=name,
        max_size=max_size,
        description=description,
        created_at=created_at,
        interaction=interaction,
        start_time=parsed_start_time,
        role_image_url=role_image_url,
    )

    content = f"<@{interaction.user.id}> has created a party for <@&{role.id}>!\n"
    if party.description:
        content += f"Description: `{party.description}`\n"

    # Don't send the party embed and view just yet, we need to get a message reference first
    await interaction.response.send_message(
        content=content,
        ephemeral=False,
        allowed_mentions=discord.AllowedMentions(),
    )

    # Get the jump URL (message link) for the party for management commands
    message = await interaction.original_response()
    party.jump_url = message.jump_url

    # Edit in the party embed and view now
    await interaction.edit_original_response(
        embed=create_embed(**party.generate_embed()),
        view=PartyView(party, party_service),
    )


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
@app_commands.describe(user="The discord user to check SSC for.")
@user_command()
async def ssc(interaction: discord.Interaction, user: Optional[discord.User] = None):
    # If no user supplied, get SSC for yourself.
    if not user:
        await interaction.response.send_message(
            embed=create_embed(
                message=f"<@{interaction.user.id}>'s Sail Social Credit: **{interaction.data['user_data']['sail_credit']}**"
            ),
        )
        return

    # If we do have a user, get that user's SSC (if exists)
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


@bot.tree.command(
    name="link-image",
    description="Link a party image to a role (or delete)",
)
@app_commands.describe(
    role="The discord role to link the image to.",
    image_url="The image URL to link to the role. Leave blank to delete the image.",
)
@user_command()
async def link_image(
    interaction: discord.Interaction, role: discord.Role, image_url: Optional[str]
):

    # Admin check.
    if not interaction.user.guild_permissions.administrator:
        await interaction.response.send_message(
            embed=create_embed(message="You need admin priviliges to use this."),
            ephemeral=True,
        )
        return

    if not image_url:
        await db.update_role_image_url(role.id, None)
        await interaction.response.send_message(
            embed=create_embed(
                message=f"Deleted image link for <@&{role.id}>.",
            ),
        )
        return

    try:
        await interaction.response.send_message(
            embed=create_embed(
                message=f"Linked image URL `{image_url}` to <@&{role.id}>.",
                image_url=image_url,
            ),
        )
        await db.update_role_image_url(role.id, image_url)

    except discord.HTTPException:
        await interaction.response.send_message(
            embed=create_embed(
                message="There was an error with the image URL, it might be malformed!",
            ),
            ephemeral=True,
        )


@bot.tree.command(
    name="adjust-ssc",
    description="Manually adjust a user's SSC. Requires admin privileges!",
)
@app_commands.describe(
    user="The discord user to adjust SSC for.",
    delta="The amount of SSC to add or deduct.",
)
@user_command()
async def adjust_ssc(interaction: discord.Interaction, user: discord.User, delta: int):

    # Check if this command is used in a server.
    if not isinstance(interaction.user, discord.Member):
        await interaction.response.send_message(
            embed=create_embed(message="This can only be used in a server."),
            ephemeral=True,
        )
        return

    # Admin check.
    if not interaction.user.guild_permissions.administrator:
        await interaction.response.send_message(
            embed=create_embed(message="You need admin priviliges to use this."),
            ephemeral=True,
        )
        return

    # Check if the user exists.
    user_info = await db.get_user(user.id)
    if not user_info:
        await interaction.response.send_message(
            embed=create_embed(message="This user hasn't used the bot before!"),
            ephemeral=True,
        )
        return

    new_ssc = max(0, user_info["sail_credit"] + delta)

    # Change and log SSC, with ADMIN as the source.
    await db.change_and_log_sail_credit(
        user.id, -1, -1, -1, user_info["sail_credit"], new_ssc, "ADMIN"
    )

    await interaction.response.send_message(
        embed=create_embed(
            message=f"Adjusted <@{user.id}>'s SSC by **{delta}**.\nNew SSC: **{new_ssc}**"
        ),
    )
    return


@bot.tree.command(
    name="conviction-log",
    description="See your or someone else's conviction log!",
)
@app_commands.describe(
    user="The user's conviction log to view.",
)
@user_command()
async def conviction_log(
    interaction: discord.Interaction, user: Optional[discord.User] = None
):

    user_id = interaction.user.id if not user else user.id
    user_name = interaction.user.display_name if not user else user.display_name
    conviction_log = await db.get_conviction_log(user_id)

    if not conviction_log:
        await interaction.response.send_message(
            embed=create_embed(message="No convictions found!"),
            ephemeral=True,
        )
        return

    pages = []
    chunks = divide_chunks(conviction_log, 10)

    for chunk in chunks:
        page_contents = []
        for log in chunk:
            page_contents.append(f"<t:{log['timestamp']}:f> **-** `{log['reason']}`")

        pages.append(
            create_embed(
                title=f"{user_name}'s Convicition Log", message="\n".join(page_contents)
            )
        )

    await interaction.response.send_message(
        embed=pages[0], view=MessageBook(interaction.user.id, pages=pages)
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

    # Run migrations
    asyncio.run(db.run_migrations())

    token_file = "test_token" if os.environ.get("SC_TEST") else "token"
    with open(token_file, "r") as f:
        token = f.read()

    patch_close()
    bot.run(token)
