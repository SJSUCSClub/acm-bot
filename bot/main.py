from bot import Bot
from dotenv import dotenv_values
import os
import discord


if __name__ == "__main__":
    config = {
        **dotenv_values(".env"),
        **dotenv_values(".env.secret"),
        **os.environ,
    }

    kwargs = {
        "intents": discord.Intents.default()
    }
    if "BOT_OWNER_IDS" in config:
        kwargs["owner_ids"] = [int(elm) for elm in config["BOT_OWNER_IDS"].split(',')]
    bot = Bot(config, config.get("BOT_COMMAND_PREFIX", "-"), **kwargs)
    bot.run(config["BOT_TOKEN"])
