from discord.ext import commands, tasks
import discord
from typing import Union, Mapping, Tuple, Optional, List
from collections import deque
from datetime import datetime
from util.checks import is_guild_owner
from util.page import PageView
import dotenv
from datetime import datetime
import asyncio


class DataHandler:
    def __init__(self) -> None:
        self.__cur_val = False
        self.data_changed = True
        self.update_timestamp = self.timestamp()

    @property
    def data(self) -> bool:
        return self.__cur_val

    @data.setter
    def data(self, val) -> None:
        self.data_changed = val != self.__cur_val
        self.__cur_val = val
        self.update_timestamp = self.timestamp()

    @staticmethod
    def timestamp():
        return datetime.now()


class Protocol(asyncio.Protocol):
    def __init__(self, dh: DataHandler) -> None:
        super().__init__()
        self.dh = dh

    def data_received(self, data: bytes) -> None:
        """
        The data received from the connection should be utf8 bytes
        that decode to either "True" or "False"
        """
        self.dh.data = data.decode() == "True"


class Monitor(commands.Cog):
    """
    Cog for interfacing with the physical hardware monitor.
    In general, the monitor should be used in the following way:

    `-link (channel)`
    """

    def __init__(
        self,
        bot: commands.Bot,
        refresh_rate: Optional[int] = 1,
        num_per_page: Optional[int] = 10,
        max_history_len: Optional[int] = 1000,
    ) -> None:
        """
        Initialize the Monitor cog

        Arguments:
            - bot: commands.Bot - the bot that owns this cog
            - refresh_rate: Optional[int] - how often to check the status of the door
            - num_per_page: Optional[int] - the number of history entries to show per page
            - max_history_len: Optional[int] - the total number of history entries to store
        """
        super().__init__()
        self.bot = bot

        # maps from the guild id to the message that was sent
        self.messages: Mapping[int, discord.Message] = {}

        self.refresh_rate = refresh_rate
        self.num_per_page = num_per_page
        self.max_history_len = max_history_len

        self.history: List[Tuple[int, str]] = []
        self.emojis = {"Open": ":unlock:", "Closed": ":lock:"}

        self.task = tasks.Loop(
            self.send_announcement,
            seconds=self.refresh_rate,
            hours=tasks.MISSING,
            minutes=tasks.MISSING,
            time=tasks.MISSING,
            count=None,
            reconnect=True,
        )
        self.server: asyncio.Server = None
        self.data_handler = DataHandler()

    async def create_status_embed(
        self, door_open: bool
    ) -> Tuple[discord.Embed, discord.File]:
        """
        Create the status embed to display the door status

        Arguments:
            - door_open: bool - whether or not the door is open
        """
        embed = discord.Embed(title="CS Club Door Status")
        file = discord.File(fp="logo.png", filename="logo.png")
        embed.set_thumbnail(url="attachment://logo.png")
        timestamp = f"<t:{int(datetime.now().timestamp())}>"

        if door_open:
            embed.color = discord.Colour.green()
            embed.description = f"MQH 227 is now open - {timestamp}"
        else:
            embed.color = discord.Colour.red()
            embed.description = f"MQH 227 is now closed - {timestamp}"

        return embed, file

    async def send_announcement(self):
        """
        Sends an announcement on the status of the door
        to the channel that the bot's door monitor is linked
        to. If the bot's door monitor isn't linked to a channel,
        nothing will happen.
        """
        # get the door status
        door_open = self.data_handler.data
        m = {False: "Closed", True: "Open"}

        for guild in self.messages:
            embed, _ = await self.create_status_embed(door_open)
            self.messages[guild] = await self.messages[guild].edit(embed=embed)

        if self.data_handler.data_changed:
            self.data_handler.data_changed = False
            self.history.append((int(datetime.now().timestamp()), m[door_open]))
            if len(self.history) > self.max_history_len:
                self.history = self.history[1:]

    @commands.command(name="link")
    @commands.check_any(is_guild_owner(), commands.is_owner())
    async def link_channel(
        self, ctx: commands.Context, channel: Union[discord.TextChannel, str]
    ):
        """
        Set the bot up to send door monitor announcements to the given channel.

        Examples:
            `-link announcements`
            `-link #announcements` where #announcements is the mention for the announcements text channel

        Arguments:
            channel - either the name of the channel or the channel's mention
        """
        if type(channel) == str:
            await ctx.send(
                f"Sorry, couldn't find the channel {channel}. Please try again, and make sure there aren't any typos."
            )
        else:
            if len(self.history) > 0:
                val = self.history[-1][1]
            else:
                val = False

            embed, file = await self.create_status_embed(val)
            self.messages[ctx.guild.id] = await channel.send(embed=embed, file=file)
            await ctx.send(
                f"Now using {channel.mention} as the place to send announcements"
            )

    @commands.command(name="testLink", aliases=["test"])
    @commands.check_any(is_guild_owner(), commands.is_owner())
    async def test_link(self, ctx: commands.Context):
        """
        Test if the bot is correctly set up to send door monitor announcements to the given channel
        """
        if ctx.guild.id in self.messages:
            await ctx.send(
                f"Correctly linked to send door monitor announcements to {self.messages[ctx.guild.id].channel.mention}"
            )
        else:
            await ctx.send(
                "Not linked to any channel. Use `-link` to link the door monitor to a channel."
            )

    @commands.command(name="start")
    @commands.is_owner()
    async def start(self, ctx: commands.Context):
        """
        Start sending door announcement messages
        to the channel this bot is linked to.
        """
        if not self.task.is_running():
            self.task.start()
        if self.server is None:
            loop = asyncio.get_event_loop()
            self.server: asyncio.Server = await loop.create_server(
                lambda: Protocol(self.data_handler),
                "localhost",
                int(dotenv.dotenv_values()["DOOR_PORT"]),
            )
            await self.server.start_serving()

        await ctx.send("Started monitoring door status.")

    async def _stop(self):
        """
        Stop all door announcement messages.
        """
        if self.server is not None:
            self.server.close()
            await self.server.wait_closed()
            self.server = None
        self.task.stop()

    @commands.command(name="stop")
    @commands.is_owner()
    async def stop(self, ctx: commands.Context):
        """
        Stop all door announcement messages
        """
        await self._stop()
        await ctx.send("Stopped monitoring door status.")

    async def get_page(self, page: int):
        """
        Get the embed that displays the `page` page of the history

        Arguments:
            - page: int - the page (0 indexed) to display the history for
        """
        embed = discord.Embed(
            title="Door History", description="", color=discord.Colour.blurple()
        )

        start = -(page + 1) * self.num_per_page
        end = -page * self.num_per_page if page != 0 else len(self.history)

        for timestamp, state in reversed(self.history[start:end]):
            embed.description += f"{self.emojis[state]} {state} - <t:{timestamp}>\n"

        embed.set_footer(text=f"Showing page {page+1}/{self.get_total_pages()}")
        return embed

    def get_total_pages(self):
        """
        Return the total number of pages that the history command will have
        """
        return len(self.history) // self.num_per_page + (
            1 if (len(self.history) % self.num_per_page) != 0 else 0
        )

    @commands.command(name="history")
    async def get_history(self, ctx: commands.Context):
        """
        Get the history of when the door was opened/closed.
        """
        await ctx.send(
            embed=await self.get_page(0),
            view=PageView(
                user=ctx.author,
                get_page=self.get_page,
                get_total_pages=self.get_total_pages,
                timeout=20,
            ),
        )

    @commands.command(name="logs")
    @commands.is_owner()
    async def get_logs(self, ctx: commands.Context, lines: int):
        """
        Get the last `lines` lines from the log file

        Examples:
        -logs 5
        -logs 10
        """
        cur = deque()
        vals = dotenv.dotenv_values()
        with open(vals["MONITOR_LOG_LOCATION"]) as f:
            line = f.readline()
            while len(line) != 0:
                cur.append(line)
                if len(cur) > lines:
                    cur.popleft()
                line = f.readline()
        joined = "".join(cur)
        await ctx.send(f"```\n{joined}\n```")

    async def cog_unload(self) -> None:
        """
        Cleanup by stopping all tasks before unloading
        """
        await self._stop()


async def setup(bot: commands.Bot):
    await bot.add_cog(Monitor(bot))
