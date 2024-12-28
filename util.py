import functools
import discord
import db

"""
A util decorator to automatically create and inject db info for a user command.
This needs to be right above the function definition, and the function's first argument must accept a discord interaction!
"""


def user_command():
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
