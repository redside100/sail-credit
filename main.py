import asyncio
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
@app_commands.describe(foo="A test description for foo", bar="A test description for bar")
@user_command()
async def ping(interaction: discord.Interaction, foo: str, bar: int):
    await interaction.response.send_message(f"Pong! {foo=} {bar=}", ephemeral=True)


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
