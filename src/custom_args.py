from inspect import signature

import discord
from discord import app_commands


# pylint: disable=abstract-method
class ColorTransformer(app_commands.Transformer):
    """Transform a string into a discord.Color"""

    # pylint: disable=arguments-differ
    async def transform(self, interaction: discord.Interaction, value: str) -> discord.Colour:
        if value == "random":
            return discord.Colour.random()
        try:
            return discord.Colour.from_str(value)
        except ValueError:
            # try to convert it from a color name
            if len(value) < 3:
                raise ValueError("Invalid color name") from None
            if not hasattr(discord.Colour, value) or not callable(getattr(discord.Colour, value)):
                raise ValueError("Invalid color name") from None
            method = getattr(discord.Colour, value)
            if len(signature(method).parameters) != 0:
                raise ValueError("Invalid color name") from None
            return method()

ColorOption = app_commands.Transform[discord.Color, ColorTransformer]
