from typing import Callable, Optional, Union

import discord
from discord.ui import button


class ConfirmView(discord.ui.View):
    "A simple view used to confirm an action"

    def __init__(self, validation: Callable[[discord.Interaction], bool],
                 ephemeral: bool=True, timeout: int=60, send_confirmation: bool=True):
        super().__init__(timeout=timeout)
        self.value: Optional[bool] = None
        self.validation = validation
        self.ephemeral = ephemeral
        self.send_confirmation = send_confirmation

    @button(label="Confirm", style=discord.ButtonStyle.green)
    async def confirm(self, interaction: discord.Interaction, _button):
        "Confirm the action when clicking"
        if not self.validation(interaction):
            return
        if self.send_confirmation:
            await interaction.response.send_message("Confirmed!", ephemeral=self.ephemeral)
        self.value = True
        self.stop()

    @button(label="Cancel", style=discord.ButtonStyle.grey)
    async def cancel(self, interaction: discord.Interaction, _button):
        "Cancel the action when clicking"
        if not self.validation(interaction):
            return
        await interaction.response.send_message("Cancelled!", ephemeral=self.ephemeral)
        self.value = False
        self.stop()

    async def disable(self, interaction: Union[discord.Message, discord.Interaction]):
        "Called when the timeout has expired"
        for child in self.children:
            child.disabled = True # type: ignore
        if isinstance(interaction, discord.Interaction):
            if interaction.message is None:
                return
            await interaction.followup.edit_message(
                interaction.message.id,
                content=interaction.message.content,
                view=self
            )
        else:
            await interaction.edit(content=interaction.content, view=self)
        self.stop()
