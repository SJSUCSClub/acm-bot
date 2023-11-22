from typing import Callable
import time
import random

# Define the GPIO pin number to which the sensor is connected
DOOR_SENSOR_PIN = 16


class PhysicalMonitor:
    """
    An abstract class for representing a physical monitor.
    """

    def __init__(
        self,
        value_function: Callable[[], bool],
        on_value_change: Callable[[bool], None],
        sleep_time: float,
    ) -> None:
        """
        Initialize the physical monitor.

        Arguments:
            - value_function - a function that returns the current state in boolean format
            - on_value_change - a function that takes a boolean that represents the
                new state of the physical monitor.
            - sleep_time - how long to wait in between reads
        """
        self.value = value_function

        self.callback = on_value_change

        self.sleep_time = sleep_time

        self.prev_state = False
        self.run = False

    def start(self) -> None:
        """
        Initialize running, blocking the current thread
        """
        # only start the task if it isn't already started
        if not self.run:
            self.run = True
            try:
                while self.run:
                    # collect value
                    val = self.value()

                    # run callback if value changed
                    if val != self.prev_state:
                        self.callback(val)

                    # update state
                    self.prev_state = val

                    # sleep
                    time.sleep(self.sleep_time)
            except Exception as e:
                print("Stopping because received exception:", e)


class DummyMonitor(PhysicalMonitor):
    """
    Dummy monitor that randomly returns open or closed
    """

    def __init__(
        self, on_value_change: Callable[[bool], None], sleep_time: float = 3
    ) -> None:
        super().__init__(lambda: random.randint(0, 1) == 0, on_value_change, sleep_time)


# type of our monitor
MONITOR_TYPE = DummyMonitor

try:
    # will raise runtime error on non-raspi devices
    import RPi.GPIO as GPIO

    class RPIMonitor(PhysicalMonitor):
        """
        Physical monitor that uses magnetic door sensors
        in order to detect if the door is open or closed.
        """

        def __init__(
            self, on_value_change: Callable[[bool], None], sleep_time: float = 0.1
        ) -> None:
            """
            Initializes the GPIO-based Raspberry Pi door monitor.

            Arguments:
                - on_value_change: Corouting - should be an async function that takes a boolean.
                    If that boolean is True, then the door is open. if False, then closed.
            """
            super().__init__(
                lambda: GPIO.input(DOOR_SENSOR_PIN) == GPIO.HIGH,
                on_value_change,
                sleep_time,
            )

            # Set the GPIO mode to BCM
            GPIO.setmode(GPIO.BCM)

            # Setup the GPIO pin as an input
            GPIO.setup(DOOR_SENSOR_PIN, GPIO.IN, pull_up_down=GPIO.PUD_UP)

        def __del__(self):
            """
            Cleans up GPIO pins
            """
            super().__del__()
            GPIO.cleanup()

    MONITOR_TYPE = RPIMonitor
    print("Using RPIMonitor.")
except ModuleNotFoundError:
    # testing on a machine that doesn't have Raspberry pi GPIO pins
    print("Using DummyMonitor.")
