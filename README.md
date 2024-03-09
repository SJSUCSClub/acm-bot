# acm-bot
This is a discord bot for the ACM chapter at SJSU. Eventually, it will link to
the ACM door monitor and give notifications on the current room availability.

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
* `sudo apt-get install python3-gpiozero`
* `source (venv)/bin/activate && pip install gpiozero`
* `cd (venv)/lib/python3.(tab)/site-packages`
* `ln -s /lib/python3/dist-packages/_lgpio(tab) .`
* `ln -s /lib/python3/dist-packages/lgpio.py .`