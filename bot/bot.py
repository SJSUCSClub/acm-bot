import discord
from discord.ext import commands
import os
from pretty_help import PrettyHelp
from typing import Union


class Bot(commands.Bot):
    def __init__(
        self,
        command_prefix,
        intents: discord.Intents = discord.Intents.all(),
        description: Union[str, None] = None,
    ) -> None:
        super().__init__(command_prefix, description=description, intents=intents)
        self.help_command = PrettyHelp(color=discord.Color.dark_purple())

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
        print("ready!")
