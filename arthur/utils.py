"""Utility functionality for King Arthur The Terrible."""

from datetime import datetime


def generate_error_message(
    *,
    title: str = "'Tis but a scratch!",
    description: str = "An error occurred",
    emote: str = ":no_entry_sign:",
) -> str:
    """Generate an error message to return to Discord."""
    return f"{emote} **{title}** {description}"


def datetime_to_discord(time: datetime, date_format: str = "f") -> str:
    """Convert a datetime object to a Discord timestamp."""
    return f"<t:{int(time.timestamp())}:{date_format}>"
