from datetime import datetime, timedelta, timezone
import functools
import time
from typing import Literal, Optional, Tuple
import discord
from pytimeparse import parse as timeparse
import db
from quickchart import QuickChart
from dateutil import parser
from zoneinfo import ZoneInfo
import re


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


def convert_to_future_datetime(dt: datetime) -> datetime:
    current_datetime = datetime.now(timezone.utc)

    if dt >= current_datetime:
        return dt

    # If this is a date in the past, add 24 hours
    if dt <= current_datetime:
        dt += timedelta(hours=24)

    return dt


def get_scheduled_datetime_from_string(
    date_input: str,
) -> Tuple[Optional[datetime], Optional[str]]:
    time_pattern = re.compile(
        r"^\s*(\d{1,2}):?(\d{2})?\s*(am|pm|AM|PM)?\s*(est|EST|pst|PST)?\s*$"
    )
    match = time_pattern.match(date_input)

    if not match:
        return None, "Invalid time format. Please use a format like `8:00 am EST`."

    groups = match.groups()
    hour = int(groups[0])
    minute = int(groups[1]) if groups[1] else 0
    am_pm = groups[2].upper() if groups[2] else None
    timezone = groups[3].upper() if groups[3] else "EST"

    if hour < 1 or hour > 12:
        return None, "Invalid hour. Please use a 12-hour format."

    if minute and (minute < 0 or minute > 59):
        return None, "Invalid minute. Please use a valid minute between 0 to 59."

    dt_timezone = (
        ZoneInfo("US/Eastern") if timezone == "EST" else ZoneInfo("US/Pacific")
    )

    dt = datetime.now(tz=dt_timezone).replace(
        hour=hour, minute=minute, second=0, microsecond=0
    )

    if (
        am_pm == "PM"
        and dt.hour < 12
        or (
            am_pm is None
            and dt + timedelta(days=1) - datetime.now(tz=dt_timezone)
            > timedelta(hours=12)
        )
    ):
        dt += timedelta(hours=12)

    dt = convert_to_future_datetime(dt)

    if dt - datetime.now(tz=dt_timezone) > timedelta(hours=12):
        return None, "The time you entered is more than 12 hours in the future."

    return convert_to_future_datetime(dt), None
