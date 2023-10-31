import discord
from discord.ext import commands
import os
from pretty_help import PrettyHelp
from typing import Union, Optional, List


class Bot(commands.Bot):
    def __init__(
        self,
        command_prefix: str,
        intents: discord.Intents = discord.Intents.all(),
        description: Union[str, None] = None,
        owner_ids: Optional[List[int]] = [],
    ) -> None:
        """
        Initialize the bot.

        Parameters
            - command_prefix: str - the prefix to use. For example: `-` or `$` are common prefixes
            - intents: discord.Intents - the priveleges that the bot has. Defaults to all
            - description: Union[str, None] - a short description of the bot, or None
            - owners: Optional[List[int]] - a list containing owner ids. This is useful for testing
                purposes when the tester may not be the creator of the bot. By passing in your
                user id as an item in owner_ids, commands that require you to be a guild owner
                or a bot owner will work.
        """
        super().__init__(command_prefix, description=description, intents=intents, case_insensitive=True)
        self.help_command = PrettyHelp(color=discord.Color.dark_purple())
        if len(owner_ids) > 0:
            self.owner_ids = owner_ids

    async def load_cogs(self):
        """
        Load all cogs in the cogs directory
        """
        cogs = os.listdir("cogs")
        if "__pycache__" in cogs:
            cogs.remove("__pycache__")  # ignore __pycache__

        print("loading cogs: ", " ".join(cogs))

        # add the cogs
        for cog in cogs:
            cog = cog.strip(".py")

            # load the cog
            await self.load_extension(f"cogs.{cog}")

        print("all cogs loaded")

    async def on_connect(self):
        print("connected!")
        await self.load_cogs()

    async def on_ready(self):
        await self.change_presence(activity=discord.Game(name="acmsjsu.org"))
        print("ready!")

    async def on_command_error(
        self, ctx: commands.Context, exception: commands.CommandError
    ) -> None:
        await ctx.send(exception)
