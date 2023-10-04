from bot.bot import Bot
from dotenv import dotenv_values

if __name__ == "__main__":
    bot = Bot("-")
    bot.run(dotenv_values()["BOT_TOKEN"])
