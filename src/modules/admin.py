import discord
from discord.ext import commands

from ..config import GUILD_ID
from ..CObot import CObot

class AdminCog(commands.Cog):
    "A few commands to manage the bot"

    def __init__(self, bot: CObot):
        self.bot = bot

    admin_main = discord.app_commands.Group(
        name="admin",
        description="Admin commands to manage the bot",
        guild_ids=[GUILD_ID.id]
    )


async def setup(bot: CObot):
    await bot.add_cog(AdminCog(bot))
