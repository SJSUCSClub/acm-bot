from discord.ext import commands
import discord
from typing import Union, Mapping
from monitor.physical_monitor import MONITOR_TYPE, PhysicalMonitor
from checks.userchecks import is_guild_owner


class Monitor(commands.Cog):
    """
    Cog for interfacing with the physical hardware monitor.
    In general, the monitor should be used in the following way:

    `-linkMonitor (channel)`
    `-startMonitor`

    However, the order doesn't strictly matter, and it can be interchanged
    without errors.
    """

    def __init__(self, bot: commands.Bot, monitor_type: type) -> None:
        super().__init__()
        self.bot = bot

        # maps from the guild id to the channel in that guild
        self.channels: Mapping[int, discord.TextChannel] = {}
        self.physical_monitor: PhysicalMonitor = monitor_type(self.send_announcement)

    @commands.command(name="linkMonitor")
    @commands.check_any(is_guild_owner(), commands.is_owner())
    async def link_channel(
        self, ctx: commands.Context, channel: Union[discord.TextChannel, str]
    ):
        """
        Set the bot up to send door monitor announcements to the given channel.
        This is necessary to see output after starting the monitor

        Examples:
            `-linkMonitor announcements`
            `-linkMonitor #announcements` where #announcements is the mention for the announcements text channel

        Arguments:
            channel - either the name of the channel or the channel's mention
        """
        if type(channel) == str:
            await ctx.send(
                f"Sorry, couldn't find the channel {channel}. Please try again, and make sure there aren't any typos."
            )
        else:
            self.channels[ctx.guild.id] = channel
            await ctx.send(
                f"Now using {channel.mention} as the place to send announcements"
            )

    @commands.command(name="testLink")
    @commands.check_any(is_guild_owner(), commands.is_owner())
    async def test_link(self, ctx: commands.Context):
        """
        Test if the bot is correctly set up to send door monitor announcements to the given channel
        """
        if ctx.guild.id in self.channels:
            await self.channels[ctx.guild.id].send(
                f"Correctly linked to send door monitor announcements to {self.channels[ctx.guild.id].mention}"
            )
        else:
            await ctx.send(
                "Not linked to any channel. Use `-linkMonitor` to link the door monitor to a channel."
            )

    @commands.command(name="startMonitor")
    @commands.check_any(is_guild_owner(), commands.is_owner())
    async def start_monitor(self, ctx: commands.Context):
        """
        Start the physical monitor so that updates on the door status
        will be sent to the channel that this bot is set to send
        door announcements to.
        """
        await self.physical_monitor.start()
        await ctx.send("Started physical monitor.")

    @commands.command(name="stopMonitor")
    @commands.check_any(is_guild_owner(), commands.is_owner())
    async def stop_monitor(self, ctx: commands.Context):
        """
        Stop the physical monitor, stopping all door announcement messages as well.
        """
        await self.physical_monitor.stop()
        await ctx.send("Stopped physical monitor.")

    async def send_announcement(self, doorOpen: bool):
        """
        Sends an announcement on the status of the door
        to the channel that the bot's door monitor is linked
        to. If the bot's door monitor isn't linked to a channel,
        nothing will happen.

        Arguments:
            - doorOpen: bool - if True, then the bot will send an announcement saying the door
                is open. Else, the bot will send an announcement saying that the door is closed.
        """
        for channel in self.channels.values():
            if doorOpen:
                embed = discord.Embed(
                    colour=discord.Colour.green(),
                    description="The door is now open!",
                )
                await channel.send(embed=embed)
            else:
                embed = discord.Embed(
                    colour=discord.Colour.red(), description="The door is now closed!"
                )
                await channel.send(embed=embed)

    async def cog_unload(self) -> None:
        """
        Stop physical monitor before unloading the cog
        """
        await self.physical_monitor.stop()


async def setup(bot: commands.Bot):
    await bot.add_cog(Monitor(bot, MONITOR_TYPE))
