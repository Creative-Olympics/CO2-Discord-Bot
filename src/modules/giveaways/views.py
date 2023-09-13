from discord import ButtonStyle, ui

from src.cobot import CObot
from src.modules.giveaways.types import GiveawayToSendData


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
