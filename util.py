import functools
from typing import Optional
import discord
import db


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


async def disable_buttons_and_stop_view(
    view: discord.ui.View,
    obj: discord.Interaction | discord.Message | discord.WebhookMessage,
):
    for component in view.children:
        if isinstance(component, discord.ui.Button):
            component.disabled = True

    if type(obj) == discord.Message or type(obj) == discord.WebhookMessage:
        await obj.edit(view=view)
    elif type(obj) == discord.Interaction:
        await obj.edit_original_response(view=view)
    else:
        raise Exception("Invalid object type passed to disable_buttons_and_stop_view")
