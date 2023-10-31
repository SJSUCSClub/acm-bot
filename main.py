from bot.bot import Bot
from dotenv import dotenv_values


if __name__ == "__main__":
    # Owners: Elliot, Kevin, Trique
    bot = Bot("-", owner_ids=[722118273784610857, 956269409805144084, 633467510833807370])
    bot.run(dotenv_values()["BOT_TOKEN"])
