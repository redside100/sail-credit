import functools
from typing import Optional
import discord
import db
from party import Party


def user_command():
    """
    A util decorator to automatically create and inject db info for a user command.
    This needs to be right above the function definition, and the function's first argument must accept a discord interaction!
    """

    def wrapper(func):
        @functools.wraps(func)
        async def wrapped(interaction: discord.Interaction, *args, **kwargs):
            user_data = await db.get_user(interaction.user.id)

            if not user_data:
                user_data = await db.create_user(interaction.user.id)

            interaction.data["user_data"] = user_data

            return await func(interaction, *args, **kwargs)

        return wrapped

    return wrapper


def create_embed(message: str, title: Optional[str] = None):
    embed = discord.Embed(color=0xFFAE00)
    embed.description = message
    if title:
        embed.title = title
    return embed


# TODO
async def calculate_sail_credit_delta(
    party: Party, user_id: int, current_ssc: int, flaked=False
):
    HISTORY_WINDOW = 86400 * 10  # 10 days

    ssc_log = await db.get_user_sail_credit_log(user_id, lookback=HISTORY_WINDOW)
    flakes = 0
    for entry in ssc_log:
        if entry["new_sail_credit"] - entry["old_sail_credit"] < 0:
            flakes += 1

    flake_ratio = flakes / len(ssc_log)


async def disable_buttons_and_stop_view(
    view: discord.ui.View, interaction: discord.Interaction
):
    for component in view.children:
        if isinstance(component, discord.ui.Button):
            component.disabled = True
    await interaction.edit_original_response(view=view)
