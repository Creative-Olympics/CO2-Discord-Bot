import discord
from discord.ext import commands

from src.cobot import CObot
from src.modules.giveaways.types import GiveawayData


class GiveawaysCog(commands.Cog):
    "Handle giveaways"

    def __init__(self, bot: CObot):
        self.bot = bot
        self.embed_color = 0x9933ff

    group = discord.app_commands.Group(
        name="giveaways",
        description="Manage giveaways in your server",
        default_permissions=discord.Permissions(manage_guild=True),
        guild_only=True
    )

    @group.command(name="list")
    async def gw_list(self, interaction: discord.Interaction, *, include_stopped: bool=False):
        "List all the giveaways in the server"
        await interaction.response.defer()
        text = ""
        now = discord.utils.utcnow()
        docs = self.bot.fb.get_giveaways() if include_stopped else self.bot.fb.get_active_giveaways()
        async for doc in docs:
            gaw: GiveawayData = doc.to_dict() # type: ignore
            if not include_stopped and gaw["ends_at"] < now:
                continue
            name = gaw["name"]
            participants_count = len(gaw["participants"])
            text += f"**{name}**  -  "
            if participants_count == 0:
                text += "no participant"
            elif participants_count == 1:
                text += "1 participant"
            else:
                text += f"{participants_count} participants"
            end_date = discord.utils.format_dt(gaw["ends_at"], "R")
            text += f" - {end_date}\n"
        embed = discord.Embed(
            title=("List of all giveaways" if include_stopped else "List of active giveaways"),
            description=text,
            color=self.embed_color
        )
        await interaction.followup.send(embed=embed)



async def setup(bot: CObot):
    "Load the cog"
    await bot.add_cog(GiveawaysCog(bot))
