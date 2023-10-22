from typing import Any, Optional, Union

from discord import ButtonStyle, Interaction, Member, Message, NotFound, User, ui

from src.cobot import CObot


class Paginator(ui.View):
    "Base class to paginate something"

    def __init__(self, client: CObot, user: Union[User, Member], stop_label: str="Quit", timeout: int=180):
        super().__init__(timeout=timeout)
        self.client = client
        self.user = user
        self.page = 1
        self.children[2].label = stop_label # type: ignore

    async def send_init(self, interaction: Interaction):
        "Build the first page, before anyone actually click"
        contents = await self.get_page_content(None, self.page)
        await self._update_buttons()
        if interaction.response.is_done():
            await interaction.followup.send(**contents, view=self)
        else:
            await interaction.response.send_message(**contents, view=self)

    async def get_page_content(self, interaction: Optional[Interaction], page: int) -> dict[str, Any]:
        "Build the page content given the page number and source interaction"
        raise NotImplementedError("get_page_content must be implemented!")

    async def get_page_count(self) -> int:
        "Get total number of available pages"
        raise NotImplementedError("get_page_count must be implemented!")


    async def interaction_check(self, interaction: Interaction, /) -> bool:
        "Check if the user is actually allowed to press that"
        result = True
        if user := interaction.user:
            result = user == self.user
        if not result:
            await interaction.response.send_message("You cannot use that!", ephemeral=True)
        return result

    async def on_error(self, interaction, error, item): # pylint: disable=arguments-differ
        self.client.dispatch("error", error, interaction)

    async def disable(self, interaction: Union[Message, Interaction]):
        "Called when the timeout has expired"
        try:
            await self._update_contents(interaction, stopped=True)
        except NotFound:
            pass
        self.stop()

    async def _set_page(self, _interaction: Interaction, page: int):
        "Set the page number starting from 1"
        count = await self.get_page_count()
        self.page = min(max(page, 1), count)

    async def _update_contents(self, interaction: Union[Message, Interaction], stopped: Optional[bool]=None):
        "Update the page content"
        if isinstance(interaction, Interaction):
            await interaction.response.defer()
        await self._update_buttons(stopped)
        if isinstance(interaction, Interaction):
            if not interaction.message:
                self.client.dispatch("error", "No message to update", interaction)
                return
            contents = await self.get_page_content(interaction, self.page)
            await interaction.followup.edit_message(
                interaction.message.id,
                view=self,
                **contents
            )
        else:
            await interaction.edit(view=self)

    async def _update_buttons(self, stopped: Optional[bool]=None):
        "Mark buttons as enabled/disabled according to current page and view status"
        stopped = self.is_finished() if stopped is None else stopped
        count = await self.get_page_count()
        # remove buttons if not required
        if count == 1:
            for child in self.children:
                self.remove_item(child)
            return
        self.children[0].disabled = (self.page == 1) or stopped     # type: ignore
        self.children[1].disabled = (self.page == 1) or stopped     # type: ignore
        self.children[2].disabled = stopped                         # type: ignore
        self.children[3].disabled = (self.page == count) or stopped # type: ignore
        self.children[4].disabled = (self.page == count) or stopped # type: ignore

    @ui.button(label='\U000025c0 \U000025c0', style=ButtonStyle.secondary)
    async def _first_element(self, interaction: Interaction, _: ui.Button):
        "Jump to the 1st page"
        await self._set_page(interaction, 1)
        await self._update_contents(interaction)

    @ui.button(label='\U000025c0', style=ButtonStyle.blurple)
    async def _previous_element(self, interaction: Interaction, _: ui.Button):
        "Go to the previous page"
        await self._set_page(interaction, self.page-1)
        await self._update_contents(interaction)

    @ui.button(label='...', style=ButtonStyle.red)
    async def _stop(self, interaction: Interaction, _: ui.Button):
        "Stop the view"
        self.stop()
        await self._update_contents(interaction)

    @ui.button(label='\U000025b6', style=ButtonStyle.blurple)
    async def _next_element(self, interaction: Interaction, _: ui.Button):
        "Go to the next page"
        await self._set_page(interaction, self.page+1)
        await self._update_contents(interaction)

    @ui.button(label='\U000025b6 \U000025b6', style=ButtonStyle.secondary)
    async def _last_element(self, interaction: Interaction, _: ui.Button):
        "Jump to the last page"
        await self._set_page(interaction, await self.get_page_count())
        await self._update_contents(interaction)
