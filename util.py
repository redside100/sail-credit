from datetime import datetime, timedelta, timezone
import functools
import time
from typing import Literal, Optional
import discord
from pytimeparse import parse as timeparse
import db
from quickchart import QuickChart
from dateutil import parser
from zoneinfo import ZoneInfo


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


def user_interaction_callback():
    """
    A util decorator to automatically create and inject db info for a user interaction callback.
    This needs to be right above the function definition, and the function's second argument must accept a discord interaction!
    """

    def wrapper(func):
        @functools.wraps(func)
        # first argument should be a self instance
        async def wrapped(self, interaction: discord.Interaction, *args, **kwargs):
            user_data = await db.get_user(interaction.user.id)

            if not user_data:
                user_data = await db.create_user(interaction.user.id)

            interaction.data["user_data"] = user_data

            return await func(self, interaction, *args, **kwargs)

        return wrapped

    return wrapper


def create_embed(
    message: str, title: Optional[str] = None, color: int | discord.Colour = 0xFFAE00
):
    embed = discord.Embed(color=color)
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


def divide_chunks(l, n):
    for i in range(0, len(l), n):
        yield l[i : i + n]


def down_scale_data(qc_data, n=500):
    if n > len(qc_data):
        return qc_data

    new_data = []
    quantum = len(qc_data) / n
    idx = 0
    while round(idx) < len(qc_data):
        new_data.append(qc_data[round(idx)])
        idx += quantum

    if round(idx) < len(qc_data) - 1:
        new_data.append(qc_data[-1])

    return new_data


async def create_ssc_graph_url(
    discord_id: str, name: str, period: Literal["1h", "6h", "12h", "1d", "7d", "30d"]
) -> str:

    start_timestamp = int(time.time()) - timeparse(period)
    credit_log = await db.get_user_sail_credit_log(discord_id, start_timestamp)

    qc_data = down_scale_data(
        [{"x": d["timestamp"] * 1000, "y": d["new_sail_credit"]} for d in credit_log],
        n=200,
    )
    qc = QuickChart()
    qc.width = 500
    qc.height = 300
    qc.device_pixel_ratio = 2.0

    qc.config = {
        "type": "line",
        "data": {"datasets": [{"fill": False, "data": qc_data}]},
        "options": {
            "elements": {"point": {"radius": 0}},
            "legend": {
                "display": False,
            },
            "title": {
                "display": True,
                "text": f"{name}'s SSC History",
            },
            "scales": {
                "xAxes": [
                    {
                        "type": "time",
                        "ticks": {
                            "maxTicksLimit": 15,
                        },
                        "time": {
                            "parser": "x",
                            "displayFormats": {
                                "hour": "MMM DD HH:mm",
                                "minute": "MMM DD HH:mm",
                                "second": "MMM DD HH:mm",
                            },
                        },
                    }
                ],
                "yAxes": [{"ticks": {"precision": 0}}],
            },
        },
    }

    return qc.get_short_url()


def get_last_reset_time():
    now = datetime.now(timezone.utc)
    if now.hour < 8:
        now -= timedelta(days=1)

    return int(now.replace(hour=8, minute=0, second=0, microsecond=0).timestamp())


def get_scheduled_datetime_from_string(date_input: str) -> datetime:

    default_datetime = datetime.now(tz=timezone.utc) + timedelta(minutes=5)
    current_timestamp = int(time.time())
    current_datetime = datetime.now(tz=timezone.utc)
    # Parse the time using dateutil parser.
    # Default timezone to EST if not included in the input string.
    zone_est = ZoneInfo("US/Eastern")
    zone_pst = ZoneInfo("US/Pacific")
    try:
        dt = parser.parse(
            date_input,
            tzinfos={
                "EST": zone_est,
                "PST": zone_pst,
                None: zone_est,
            },
        )

        dt = dt.astimezone(timezone.utc)

    except parser.ParserError:
        return default_datetime

    # If the parser interpretted it as a date in the past, add 12 hours, up to 2 times.
    for _ in range(2):
        if dt < current_datetime:
            dt += timedelta(hours=12)

    # If the date is still in the past, default.
    if dt < current_datetime:
        return default_datetime

    # If the date is less than 10 seconds away, set it to 10 seconds away.
    if int(dt.timestamp()) - current_timestamp < 10:
        return current_datetime + timedelta(seconds=10)

    # If the date is more than 12 hours away, set it to 12 hours away.
    if int(dt.timestamp()) - current_timestamp > 3600 * 12:
        return current_datetime + timedelta(hours=12)

    return dt
