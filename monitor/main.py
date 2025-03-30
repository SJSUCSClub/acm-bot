from physical_monitor import RPIMonitor, DummyMonitor
import socket
from urllib.parse import urlparse
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
        self.last_tcp_attempt_failed = False
        vals = dotenv.dotenv_values()
        # https://bugs.python.org/issue754016
        # We could use rsplit(':', 1) with some extra checks for IPv6, but that's more logic ensure correct
        tcp_endpoint = urlparse('//' + vals["DOOR_TCP_ENDPOINT"])
        self.tcp_host = tcp_endpoint.hostname
        self.tcp_port = tcp_endpoint.port
        self.http_endpoint = vals.get("DOOR_HTTP_ENDPOINT", None)

    def __call__(self, open: bool):
        self.send_tcp_update(open)
        if self.last_openness != open:
            self.last_openness = open

            self.send_http_update(open)

    def send_tcp_update(self, open: bool):
        """
        Post a status update to the server

        Arguments:
            - open: bool - whether the door is currently open
        """

        s = socket.socket()
        try:
            s.connect((self.tcp_host, self.tcp_port))
        except ConnectionRefusedError:
            if not self.last_tcp_attempt_failed:
                logger.info(
                    "Failed to connect to the server since %s",
                    datetime.now().isoformat(),
                )
                self.last_tcp_attempt_failed = True
            return

        # make sure we sent the value
        msg = str(open).encode()
        assert s.send(msg) == len(msg)
        if self.last_tcp_attempt_failed:
            self.last_tcp_attempt_failed = False
            logger.info(
                "Able to connect to the server since %s", datetime.now().isoformat()
            )

    def send_http_update(self, open: bool):
        if self.http_endpoint is None:
            return

        try:
            headers = {"Content-Type": "text/plain"}
            r = requests.post(self.http_endpoint, headers=headers, data=("open" if open else "closed"))
            r.raise_for_status()
        except (requests.ConnectionError, requests.HTTPError):
            logger.info(
                "Failed to send to HTTP endpoint %s",
                self.http_endpoint
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
