from physical_monitor import MONITOR_TYPE
import requests
import dotenv


def post_status(open: bool) -> None:
    """
    Post a status update to the thing

    Arguments:
        - open: bool - whether or not the door is currently open
    """
    resp = requests.post(dotenv.dotenv_values()["DOOR_URL"], json={"open": open})
    assert resp.status_code == 200  # we want it acknowledged


if __name__ == "__main__":
    monitor = MONITOR_TYPE(on_value_change=post_status)
    monitor.start()
