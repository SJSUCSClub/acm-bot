from typing import Callable
from abc import ABC, abstractmethod
import time
from logging import Logger
from datetime import datetime
import random

# Define the GPIO pin number to which the sensor is connected
DOOR_SENSOR_PIN = 16


class PhysicalMonitor(ABC):
    """
    An abstract class for representing a physical monitor.
    """

    def __init__(
        self, refresh_every: float, callback: Callable[[bool], None], logger: Logger
    ) -> None:
        """
        Initialize the physical monitor.

        Arguments:
            - refresh_every - how often, in seconds, to send the current value
            - callback - a function that takes a boolean that represents the
                new state of the physical monitor.
        """
        self.refresh_every = refresh_every
        self.callback = callback
        self.run = False
        self.logger = logger

    @abstractmethod
    def value(self) -> bool:
        """
        Returns the current state, either True for open or False for closed
        """

    def start(self) -> None:
        """
        Initialize running, blocking the current thread
        """
        if not self.run:
            self.run = True
            try:
                while self.run:
                    val = self.value()
                    self.callback(val)
                    time.sleep(self.refresh_every)
            except KeyboardInterrupt:
                self.logger.info("Stopping due to keyboard interrupt.")


class DummyMonitor(PhysicalMonitor):
    """
    Dummy monitor that randomly returns open or closed
    """

    def __init__(
        self, refresh_every: float, callback: Callable[[bool], None], logger: Logger
    ):
        super().__init__(refresh_every, callback, logger)

    def value(self):
        return random.randint(0, 1) == 0


class RPIMonitor(PhysicalMonitor):
    """
    Physical monitor that uses magnetic door sensors
    in order to detect if the door is open or closed.
    """

    def __init__(
        self, refresh_every: float, callback: Callable[[bool], None], logger: Logger
    ):
        from gpiozero import Button

        super().__init__(refresh_every, callback, logger)
        self.button = Button(DOOR_SENSOR_PIN)
        self.button.when_pressed = lambda: self.logger.debug(
            "Door closed at %s", datetime.now().isoformat()
        )
        self.button.when_released = lambda: self.logger.debug(
            "Door open at %s", datetime.now().isoformat()
        )

    def value(self):
        return self.button.value == 0  # 1 if pressed (closed), 0 if not (open)
