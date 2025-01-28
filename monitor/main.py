from physical_monitor import RPIMonitor, DummyMonitor
import socket
import dotenv
import logging
from datetime import datetime
import os

logger = logging.getLogger(__name__)


class StatusUpdater:
    def __init__(self):
        self.vals = dotenv.dotenv_values()
        self.last_attempt_failed = False

    def __call__(self, open: bool):
        """
        Post a status update to the server

        Arguments:
            - open: bool - whether or not the door is currently open
        """

        s = socket.socket()
        vals = dotenv.dotenv_values()
        try:
            s.connect((vals["DOOR_URL"], int(vals["DOOR_PORT"])))
        except ConnectionRefusedError:
            if not self.last_attempt_failed:
                logger.info(
                    "Failed to connect to the server since %s",
                    datetime.now().isoformat(),
                )
                self.last_attempt_failed = True
            return

        # make sure we sent the value
        assert s.send(str(open).encode()) == len(str(open).encode())
        if self.last_attempt_failed:
            self.last_attempt_failed = False
            logger.info(
                "Able to connect to the server since %s", datetime.now().isoformat()
            )


def main():
    # configure root logger
    logging.basicConfig(
        filename=os.path.join(os.path.dirname(__file__), "monitor.log"),
        level=logging.DEBUG,
        filemode="w",
    )
    logger.info("Started monitor service")

    # set up values
    post_status = StatusUpdater()

    # load correct monitor
    vals = dotenv.dotenv_values()
    try:
        monitor = RPIMonitor(float(vals["REFRESH_EVERY"]), post_status, logger)
        logger.info("Using RPIMonitor.")
    except ModuleNotFoundError:
        # testing on a machine that doesn't have Raspberry pi GPIO pins
        monitor = DummyMonitor(float(vals["REFRESH_EVERY"]), post_status, logger)
        logger.info("Using DummyMonitor.")
    # begin process
    monitor.start()


if __name__ == "__main__":
    main()
