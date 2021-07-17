"""Utility functionality for King Arthur."""

from discord import Embed
from discord.colour import Colour


def generate_error_embed(title: str = "'Tis but a scratch!", description: str = "An error occurred") -> Embed:
    """Generate an error embed to return to Discord."""
    return Embed(
        title=title,
        description=description,
        colour=Colour.red()
    )
