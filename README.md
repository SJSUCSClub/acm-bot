# acm-bot
This is a discord bot for the ACM chapter at SJSU. Eventually, it will link to
the ACM door monitor and give notifications on the current room availability.

## Contributing
This project uses a Cog and Extension setup. The purpose of using Cogs and
Extensions is to group related commands with each other and allow easy loading/reloading
of commands without having to restart the bot (sending `-reload (cog)` will reload the specified cog).

To add a cog, add a file in the directory `cogs`. The file should contain a class that
inherits from `commands.Cog` and a function `setup` that adds that cog to the Bot.
