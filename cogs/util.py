from discord.ext import commands
import discord


class Util(commands.Cog):
    """
    Utility commands
    """

    def __init__(self, bot: commands.Bot) -> None:
        self.bot = bot

    @commands.command(name="ping")
    async def ping(self, ctx: commands.Context) -> None:
        """
        Get the bot's latency, in milliseconds
        """
        await ctx.send(f"Pong 🏓! Latency was {int(self.bot.latency * 1000)} ms")

    @commands.command(name="reload")
    async def reload(self, ctx: commands.Context, *cogs: str) -> None:
        """
        Reload cogs by name, or `all`

        Example usage:
        `-reload all` - reloads all cogs
        `-reload util` - reloads the util cog

        Arguments:
            cogs - the cogs to reload, separated by a space
        """
        reloaded_cogs = []
        loaded_cogs = []
        errors = []

        for cog in cogs:
            cog_file = cog.strip().lower()
            cog_name = cog_file.title()
            already_loaded = f"cogs.{cog_file}" in self.bot.extensions

            # load / reload the extension, or catch an error
            try:
                if already_loaded:
                    await self.bot.reload_extension(f"cogs.{cog_file}")
                    reloaded_cogs.append(cog_name)
                else:
                    await self.bot.load_extension(f"cogs.{cog_file}")
                    loaded_cogs.append(cog_name)
            except Exception as e:
                if already_loaded:
                    errors.append(f"Failed to reload {cog_name} because {e}")
                else:
                    errors.append(f"Failed to load {cog_name} because {e}")

        # send results
        if len(cogs) > 0:
            embed = discord.Embed(
                title="Reload Results", description="", color=discord.Color.blue()
            )
            if len(reloaded_cogs) > 0:
                embed.description += "### Reloaded the following cogs:\n"
                embed.description += "\n".join([f"- {cog}" for cog in reloaded_cogs])
            if len(loaded_cogs) > 0:
                embed.description += "### Loaded the following cogs:\n"
                embed.description += "\n".join([f"- {cog}" for cog in loaded_cogs])
            if len(errors) > 0:
                embed.description += "### Got the following errors:\n"
                embed.description += "\n".join([f"- {error}" for error in errors])

            await ctx.send(embed=embed)
        else:
            await ctx.send("An argument is required!")

    @commands.command(name="remove")
    async def remove(self, ctx: commands.Context, *cogs: str):
        """
        Remove cogs by name, or `all`

        Example usage:
        `-remove all` - removes all cogs
        `-remove util` - removes the util cog

        Arguments:
            cogs - the cogs to remove, separated by a space
        """
        removed_cogs = []
        nonloaded_cogs = []
        errors = []

        for cog in cogs:
            cog_file = cog.strip().lower()
            cog_name = cog_file.title()

            # remove the extension, or catch an error
            try:
                if f"cogs.{cog_file}" in self.bot.extensions:
                    await self.bot.unload_extension(f"cogs.{cog_file}")
                    removed_cogs.append(cog_name)
                else:
                    nonloaded_cogs.append(cog_name)
            except Exception as e:
                errors.append(f"Failed to remove {cog_name} because {e}")

        # send results
        if len(cogs) > 0:
            embed = discord.Embed(
                title="Reload Results", description="", color=discord.Color.blue()
            )
            if len(removed_cogs) > 0:
                embed.description += "### Removed the following cogs:\n"
                embed.description += "\n".join([f"- {cog}" for cog in removed_cogs])
            if len(nonloaded_cogs) > 0:
                embed.description += (
                    "### The following cogs weren't loaded to begin with:\n"
                )
                embed.description += "\n".join([f"- {cog}" for cog in nonloaded_cogs])
            if len(errors) > 0:
                embed.description += "### Got the following errors:\n"
                embed.description += "\n".join([f"- {error}" for error in errors])

            await ctx.send(embed=embed)
        else:
            await ctx.send("An argument is required!")


async def setup(bot: commands.Bot):
    await bot.add_cog(Util(bot))
