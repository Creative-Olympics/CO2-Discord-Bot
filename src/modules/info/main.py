import discord
from discord import app_commands
from discord.ext import commands

from src.cobot import CObot, COInteraction

ANNOUNCEMENT_CHANNEL_ID = 846007606845636608

class InfoCog(commands.Cog):
    "A few commands to get more info about the event"

    def __init__(self, bot: CObot):
        self.bot = bot

    @app_commands.command(name="donation-link")
    async def get_donation_link(self, interaction: COInteraction):
        "Get to know where to donate!"
        if not await self.bot.fb.check_has_event_started():
            await interaction.response.send_message(
                f"The event hasn't started yet, keep an eye on <#{ANNOUNCEMENT_CHANNEL_ID}> for more info!"
            )
            return
        if await self.bot.fb.check_has_event_finished():
            await interaction.response.send_message(
                "The event is over, thanks for your support!"
            )
            return
        url = self.bot.config["DONATION_URL"]
        embed = discord.Embed(
            title="Donation link",
            description=f"Here's the link to donate: [creative-olympics.org/donate]({url})",
            color=discord.Color.green()
        )
        await interaction.response.send_message(embed=embed)


async def setup(bot: CObot):
    await bot.add_cog(InfoCog(bot))
