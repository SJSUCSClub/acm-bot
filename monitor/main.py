from physical_monitor import RPIMonitor, DummyMonitor
import socket
import requests
import dotenv
import logging
from datetime import datetime
import os

logger = logging.getLogger(__name__)


class StatusUpdater:
    def __init__(self):
        self.vals = dotenv.dotenv_values()
        self.last_openness = None
        self.last_attempt_failed = False

    def __call__(self, open: bool):
        if self.last_openness != open:
            self.last_openness = open
            self.send_update(open)

    def send_update(self, open: bool):
        """
        Post a status update to the server

        Arguments:
            - open: bool - whether or not the door is currently open
        """

        s = socket.socket()
        vals = dotenv.dotenv_values()
        try:
            # TODO rename this to DOOR_ADDR "host:port" pair, it's not a (colloquial) URL!
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
        msg = str(open).encode()
        assert s.send(msg) == len(msg)
        if self.last_attempt_failed:
            self.last_attempt_failed = False
            logger.info(
                "Able to connect to the server since %s", datetime.now().isoformat()
            )

        endpoint = vals.get("DOOR_HTTP_ENDPOINT", None)
        if endpoint is not None:
            try:
                status_text = 'open' if open else 'closed'
                headers = {"Content-Type": "text/plain"}
                r = requests.post(endpoint, headers=headers, data=status_text)
                r.raise_for_status()
            except (requests.ConnectionError, requests.HTTPError,):
                logger.info(
                    "Failed to send to HTTP endpoint %s",
                    endpoint
                )
                # Do not set last_attempt_failed, this is an optional secondary mechanism

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
