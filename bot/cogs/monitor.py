from discord.ext import commands, tasks
import discord
from typing import Union, Mapping, Tuple, Optional, List, NamedTuple
from collections import deque
from datetime import datetime
from util.checks import is_guild_owner
from util.page import PageView
from datetime import datetime
import asyncio
from dataclasses import dataclass
import textwrap


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


class HistoryPoint(NamedTuple):
    timestamp: int  # the integer value of the seconds since the epoch
    is_open: bool  # whether the door was open at this time


class Monitor(commands.Cog):
    """
    Cog for interfacing with the physical hardware monitor.

    **Terminology:** "Monitor" is the thing which watches over some physical objects, generating "status" of each.
    The monitor pushes "updates" of changed statuses over network to this bot.
    Each status is then displayed in "tracked messages" on Discord, which are edited to reflect each update.

    In general, the monitor should be used in the following way:

    `-link (channel)`
    """

    def __init__(
        self,
        bot: commands.Bot,
        tracking_interval: Optional[int] = 60,
        num_per_page: Optional[int] = 10,
        max_history_len: Optional[int] = 1000,
    ) -> None:
        """
        Initialize the Monitor cog

        Arguments:
            - bot: commands.Bot - the bot that owns this cog
            - tracking_interval: Optional[int] - how often to update the status of the door, in seconds
            - num_per_page: Optional[int] - the number of history entries to show per page
            - max_history_len: Optional[int] - the total number of history entries to store
        """
        super().__init__()
        self.bot = bot

        self.tracked_messages: Mapping[int, discord.Message] = {}
        """List of messages displaying the current monitor status. Persistent."""
        self.tracking_interval = tracking_interval
        """Number of seconds between editing tracked messages to reflect the current status."""

        self.history: List[HistoryPoint] = []
        self.num_per_page = num_per_page
        self.max_history_len = max_history_len

        self.task: tasks.Loop = None
        self.server: asyncio.Server = None
        self.data_handler = DataHandler()

    async def cog_load(self):
        """
        Startup relevant services
        """
        loop = asyncio.get_event_loop()
        self.server: asyncio.Server = await loop.create_server(
            lambda: Protocol(self.data_handler),
            "localhost",
            int(self.bot.config["BOT_MONITOR_LISTEN_PORT"]),
        )
        await self.server.start_serving()

    @commands.Cog.listener()
    async def on_ready(self):
        await self.load_persistent_state()

        self.task = tasks.Loop(
            self.send_announcement,
            seconds=self.tracking_interval,
            hours=tasks.MISSING,
            minutes=tasks.MISSING,
            time=tasks.MISSING,
            count=None,
            reconnect=True,
        )
        self.task.start()

    async def cog_unload(self):
        """
        Cleanup by stopping all tasks before unloading
        """
        if self.server is not None:
            self.server.close()
            await self.server.wait_closed()
            self.server = None
        self.task.stop()

    async def load_persistent_state(self):
        """
        Load persistent
        :return:
        """
        # Yes, this means if this class is renamed, the file needs to be moved.
        # Don't care.
        # This is fancy and that's all it matters (and that realistically nobody except ACM club) deploys this thing.
        persistent_state = self.bot.load_state(type(self).__name__)
        # When the state file doesn't exist, skip loading
        if len(persistent_state) == 0:
            return

        self.tracked_messages = {
            int(guild_id): await self.bot.get_guild(int(guild_id)).get_channel(msg["channel"]).fetch_message(msg["message"])
            for guild_id, msg in persistent_state["tracked_messages"].items()
        }
        self.history = [
            HistoryPoint(int(elm["timestamp"]), bool(elm["is_open"]))
            for elm in persistent_state["history"]
        ]

    def save_persistent_state(self):
        data = {
            "history": [point._asdict() for point in self.history],
            "tracked_messages": {
                guild_id: {"channel": msg.channel.id, "message": msg.id}
                for guild_id, msg in self.tracked_messages.items()
            },
        }
        self.bot.save_state(type(self).__name__, data)

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

        for guild in self.tracked_messages:
            embed, _ = await self.create_status_embed(door_open)
            self.tracked_messages[guild] = await self.tracked_messages[guild].edit(embed=embed)

        if self.data_handler.data_changed:
            self.data_handler.data_changed = False
            self.history.append(
                HistoryPoint(int(datetime.now().timestamp()), door_open)
            )
            if len(self.history) > self.max_history_len:
                self.history = self.history[1:]
            self.save_persistent_state()

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
                is_open = self.history[-1].is_open
            else:
                is_open = False

            embed, file = await self.create_status_embed(is_open)
            self.tracked_messages[ctx.guild.id] = await channel.send(embed=embed, file=file)
            self.save_persistent_state()
            await ctx.send(
                f"Now using {channel.mention} as the place to send announcements"
            )

    @commands.command(name="testLink", aliases=["test"])
    @commands.check_any(is_guild_owner(), commands.is_owner())
    async def test_link(self, ctx: commands.Context):
        """
        Test if the bot is correctly set up to send door monitor announcements to the given channel
        """
        if ctx.guild.id in self.tracked_messages:
            await ctx.send(
                f"Correctly linked to send door monitor announcements to {self.tracked_messages[ctx.guild.id].channel.mention}"
            )
        else:
            await ctx.send(
                "Not linked to any channel. Use `-link` to link the door monitor to a channel."
            )

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

        for point in reversed(self.history[start:end]):
            openness = "Open" if point.is_open else "Closed"
            emoji = ":unlock:" if point.is_open else ":lock:"
            embed.description += f"{emoji} {openness} - <t:{point.timestamp}>\n"

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
        with open(self.bot.config["MONITOR_LOG_LOCATION"]) as f:
            line = f.readline()
            while len(line) != 0:
                cur.append(line)
                if len(cur) > lines:
                    cur.popleft()
                line = f.readline()
        joined = "".join(cur)
        await ctx.send(f"```\n{joined}\n```")

    @commands.command(name="status")
    async def status(self, ctx: commands.Context):
        """
        Get the status of the monitor

        Example:
        -status
        """

        # arbitrary threshold before "no longer receiving live messages"
        THRESHOLD = 10  # 10 seconds
        started = self.server is not None
        linked = ctx.guild.id in self.tracked_messages
        still_receiving = (
            len(self.history) > 0
            and datetime.now().timestamp()
            - self.data_handler.update_timestamp.timestamp()
            < THRESHOLD
        )
        good = started and linked and still_receiving

        # create and send embed
        embed = discord.Embed(
            title=f"{'' if good else 'not '}functioning Properly".title(),
            description="",
            color=discord.Colour.green() if good else discord.Colour.red(),
        )
        embed.description = textwrap.dedent(
            f"""
            * Started: {started}
            * Linked to a channel: {linked}
            * Still receiving monitor messages: {still_receiving}
            """
        )
        await ctx.send(embed=embed)


async def setup(bot: commands.Bot):
    await bot.add_cog(Monitor(bot))
