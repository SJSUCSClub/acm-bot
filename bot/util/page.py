import discord
from typing import Callable, Optional, List, Awaitable


class PageView(discord.ui.View):
    children: List[discord.ui.Button]

    def __init__(
        self,
        user: discord.User,
        get_page: Callable[[int], Awaitable[discord.Embed]],
        get_total_pages: Callable[[], int],
        timeout: Optional[float] = 180,
    ):
        """
        Create the PageView

        Arguments:
            - user: discord.User - the user who will be able to control the interaction
            - get_page: Callable[[], Awaitable[discord.Embed]] - the callable that takes an integer
                parameter representing the current page and returns an awaitable
                that returns the given page (a discord.Embed)
            - get_total_pages: Callable[[], int] - a callable that returns the total
                number of pages
            - timeout: float - how long to wait, in seconds, before considering the page stale. Defaults
                to 180.
        """
        super().__init__(timeout=timeout)
        self.user = user
        self.get_page = get_page
        self.get_total_pages = get_total_pages
        self.page = 0

        self.update_buttons()
        self.interaction = None

    async def interaction_check(self, interaction: discord.Interaction) -> bool:
        """
        Check for the interaction
        """
        if interaction.user == self.user:
            return True
        else:
            emb = discord.Embed(
                description=f"Only the author of the command can perform this action.",
                colour=discord.Colour.red(),
            )
            await interaction.response.send_message(embed=emb, ephemeral=True)
            return False

    def update_buttons(self):
        # reset disabled
        self.children[0].disabled = False
        self.children[1].disabled = False

        # add 1 since self.page is from 0 to 1-self.get_total_pages
        if self.page + 1 >= self.get_total_pages():
            # can't go right anymore; disable next button
            self.children[1].disabled = True
        if self.page == 0:
            # can't go left anymore; disable prev button
            self.children[0].disabled = True

    async def edit_page(self, interaction: discord.Interaction):
        emb = await self.get_page(self.page)
        self.update_buttons()
        await interaction.response.edit_message(embed=emb, view=self)

    @discord.ui.button(emoji="◀️", style=discord.ButtonStyle.blurple)
    async def previous(self, interaction: discord.Interaction, button: discord.Button):
        self.page -= 1
        await self.edit_page(interaction)

    @discord.ui.button(emoji="▶️", style=discord.ButtonStyle.blurple)
    async def next(self, interaction: discord.Interaction, button: discord.Button):
        self.page += 1
        await self.edit_page(interaction)

    async def on_timeout(self):
        # disable buttons on timeout
        for item in self.children:
            item.disabled = True

        self.stop()
