import asyncio
from typing import Optional
from discord import app_commands
import discord
from discord.ext import commands
import db
from util import user_command

intents = discord.Intents.default()
bot = commands.Bot(
    command_prefix="/",
    intents=intents,
    case_insensitive=False,
)


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
    party_name="Optional name for your party.",
    party_description="Optional description for your party.",
    party_size="The number of people you want in your party.",
    party_time="The time you want to start the party.",
)
async def create_party(
    interaction: discord.Interaction,
    party_type: str,
    party_name: Optional[str],
    party_size: int = 5,
    party_description: str = "",
):
    user = interaction.user

    user_id = user.id
    if not party_name:
        # Unsure of whether to use name, or global_name.
        party_name = f"{user.name}'s {party_type} Party"

    await interaction.response.send_message(f"This is your message: ", ephemeral=False)


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
