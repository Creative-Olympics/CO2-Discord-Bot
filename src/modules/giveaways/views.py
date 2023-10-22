from math import ceil
from typing import Union

from discord import ButtonStyle, Embed, Member, User, ui

from src.cobot import CObot
from src.modules.giveaways.types import GiveawayData, GiveawayToSendData
from src.utils.paginator_view import Paginator


class GiveawayView(ui.View):
    "Allows users to join a giveaway"

    def __init__(self, bot: CObot, data: GiveawayToSendData, button_label: str):
        super().__init__(timeout=None)
        self.bot = bot
        self.data = data
        gaw_id = data["id"]
        enter_btn = ui.Button(
            label=button_label,
            style=ButtonStyle.green,
            custom_id=f"gaw-{gaw_id}"
        )
        self.add_item(enter_btn)


class ParticipantsPaginator(Paginator):
    "Allows users to see the participants of a giveaway"
    def __init__(self, client: CObot, embed_color: int, user: Union[User, Member], gaw: GiveawayData, participants: list[int]):
        super().__init__(client, user)
        self.embed_color = embed_color
        self.title = f"Participants of {gaw['name']}"
        self.participants = participants
        self.page_count = ceil(len(participants) / 20)

    async def get_page_count(self) -> int:
        "Get total number of available pages"
        return self.page_count

    async def get_page_content(self, interaction, page):
        "Build the page content given the page number and source interaction"
        lower_index = (page - 1) * 20
        upper_index = min(page * 20, len(self.participants))
        participants_count = len(self.participants)
        page_participants = [
            f"<@{user_id}> ({user_id})"
            for user_id in self.participants[lower_index:upper_index]
        ]
        if participants_count == 1:
            desc_header = "### 1 participant"
        elif participants_count <= 20:
            desc_header = f"### {participants_count} participants"
        else:
            desc_header = f"### Participants {lower_index+1}-{upper_index} out of {participants_count}"
        embed = Embed(
            title=self.title,
            description=desc_header + "\n\n" + "\n".join(page_participants),
            color=self.embed_color
        )
        embed.set_footer(text=f"Page {page}/{self.page_count}")
        return {"embed": embed}
