# acm-bot

This is a discord bot for the ACM chapter at SJSU. It links
the ACM door monitor to the ACM discord server, providing notifications
on the current room availability.

## Getting Started

First, make sure to install all the requirements. You can do so by running the following command
from the root of the repository:

```sh
pip install -r requirements.txt
```

From there, the project is divided into two services, the physical hardware monitor and the discord bot. They are currently tightly coupled,
and must be run on the same machine, although this may get changed in future versions.

### Physical Monitor

Configure `.env` variables:

- `DOOR_TCP_ENDPOINT` (required)

  Destination `host:port` pair to send door updates to.

- `DOOR_HTTP_ENDPOINT` (optional)

  Destination HTTP URL to send door updates to. The update will be sent as a `POST` with `Content-Type: text/plain` and `Body:` "open" or "close". 
  If unspecified, this feature is disabled.

- `REFRESH_EVERY` (required)

  How often to send door status.

In order to run the monitor, simply run the below commands:

```sh
cd monitor
python3 main.py
```

### Discord Bot

Configure `.env` variables:

- `BOT_TOKEN` (required)

  Discord bot token

- `BOT_OWNER_IDS` (optional)

  List of Discord user IDs that are authorized to send commands to this bot. If unspecified, all users are authorized.
  Contents are simply passed to [discord.py](https://discordpy.readthedocs.io/en/stable/ext/commands/api.html#discord.ext.commands.Bot.owner_ids).

- `BOT_COMMAND_PREFIX` (optional)

  Your usual Discord bot command prefix. If unspecified, uses `-` (ASCII minus).

- `BOT_MONITOR_LISTEN_PORT` (required)

  TCP port at which the bot listens for monitor updates. TCP address is always any.
  If unspecified, this feature will be disabled (as-if the monitor is not running).

  In a normal deployment where the bot and the monitor runs on the same machine, you probably want to set this to the same port as `DOOR_TCP_ENDPOINT`.

- `MONITOR_LOG_LOCATION` (optional)

  /path/to/monitor.log, at which this bot reads logs from 

In order to run the discord bot, simply run the below commands:

```sh
cd bot
python3 main.py
```

### Example

In total, your `.env` file, which should be placed in the root of this repository,
should look something like the following file:

```
BOT_TOKEN = MY_BOT_TOKEN
BOT_MONITOR_LISTEN_PORT = 3000
DOOR_TCP_ENDPOINT = localhost:3000
DOOR_HTTP_ENDPOINT = https://example.com/the-door?token=123456
REFRESH_EVERY = 1
MONITOR_LOG_LOCATION = /home/acmcs/acm-bot/monitor/monitor.log
```

## Contributing

This project uses a Cog and Extension setup. The purpose of using Cogs and
Extensions is to group related commands with each other and allow easy loading/reloading
of commands without having to restart the bot (sending `-reload (cog)` will reload the specified cog).

To add a cog, add a file in the directory `cogs`. The file should contain a class that
inherits from `commands.Cog` and a function `setup` that adds that cog to the Bot.

## Hardware Wiring Schematic

For the Raspberry Pi to be wired up correctly with the door sensors, the long wire
from the door sensor must be wired up to `GPIO 16`. The short wire from the door sensor must
be wired up to `GND`.

What this looks like in practice:

- door sensor's short wire &rarr; female to female connector &rarr; black extender wire &rarr; female to female connector &rarr;
  the `GND` pin on the Raspberry Pi (the 4th pin from the bottom on the right)
- door sensor's long wire &rarr; female to female connector &rarr; red extender wire &rarr; female to female connector &rarr;
  the `GPIO 16` pin on the Raspberry Pi (the 3rd pin from the bottom on the right)

![pinout](image.png)

## Raspi 5 setup

To set up the repository on a raspberry pi 5 to use a physical monitor, follow the below steps to get `gpiozero` in a venv.

- `sudo apt-get install python3-gpiozero`
- `source (venv)/bin/activate && pip install gpiozero`
- `cd (venv)/lib/python3.(tab)/site-packages`
- `ln -s /lib/python3/dist-packages/_lgpio(tab) .`
- `ln -s /lib/python3/dist-packages/lgpio.py .`

In order to add the services, simply run the following commands from the root of the repository:

```sh
cd ./services
# make the startup files executable
chmod +x discordbotservice.sh
chmod +x monitorservice.sh
# symlink the service files
sudo ln -s /home/acmcs/acm-bot/services/discordbot.service /etc/systemd/system/
sudo ln -s /home/acmcs/acm-bot/services/monitor.service /etc/systemd/system/
sudo ln -s /home/acmcs/acm-bot/services/gitpull.service /etc/systemd/system/
# enable services
sudo systemctl enable gitpull
sudo systemctl enable discordbot
sudo systemctl enable monitor
```

Note that this assumes that you have cloned the repository in the home directory and that the user is `acmcs`.
