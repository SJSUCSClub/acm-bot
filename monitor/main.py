from physical_monitor import MONITOR_TYPE
import socket
import dotenv


def post_status(open: bool) -> None:
    """
    Post a status update to the thing

    Arguments:
        - open: bool - whether or not the door is currently open
    """
    s = socket.socket()
    try:
        vals = dotenv.dotenv_values()
        s.connect((vals["DOOR_URL"], int(vals["DOOR_PORT"])))
    except ConnectionRefusedError:
        return

    # make sure we sent the value
    assert s.send(str(open).encode()) == len(str(open).encode())


if __name__ == "__main__":
    monitor = MONITOR_TYPE(on_value_change=post_status)
    monitor.start()
