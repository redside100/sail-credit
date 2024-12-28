import asyncio
from typing import Optional
from discord import app_commands
import discord
from discord.ext import commands
import db
from party import Party, PartyService
import config
from util import user_command, create_embed
from views import PartyView

intents = discord.Intents.default()
bot = commands.Bot(
    command_prefix="/",
    intents=intents,
    case_insensitive=False,
)

# Services
party_service = PartyService()


@bot.tree.command(
    name="ping",
    description="Pong!",
)
@app_commands.describe(
    foo="A test description for foo", bar="A test description for bar"
)
@user_command()
async def ping(interaction: discord.Interaction, foo: str, bar: int):
    await interaction.response.send_message(f"Pong! {foo=} {bar=}", ephemeral=True)


@bot.tree.command(
    name="party-up",
    description="Creates a party, allowing others to let you know they want to join!",
)
@app_commands.describe(
    type="The type of party you're creating (e.g. Gartic Phone, RotMG)",
    name="The name of the party (optional)",
    size="The size of the party (default is 5)",
    description="Any additional information you want to provide about the party.",
)
async def create_party(
    interaction: discord.Interaction,
    type: str,
    name: Optional[str],
    size: Optional[int],
    description: Optional[str],
):
    party: Party = party_service.create_party(
        user=interaction.user,
        type=type,
        name=name,
        size=size,
        description=description,
    )

    # If the party type is supported, send out a ping to the channel.
    role_id = config.SUPPORTED_PARTY_TYPES.get(type.upper())
    if role_id:
        party_type_label = f"<@&{role_id}>"
    else:
        party_type_label = f"`{party.type}`"

    # TODO: It doesn't seem to be mentioning the role correctly.
    content = f"<@{interaction.user.id}> has created a party for {party_type_label}!\n"
    if party.description:
        content += f"Description: `{party.description}`\n"

    await interaction.response.send_message(
        content=content,
        embed=create_embed(PartyService.generate_embed(party)),
        view=PartyView(party),
        ephemeral=False,
    )


@bot.event
async def on_ready():
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
