from ...lib import fusionAddInUtils as futil
from .server import FusionServer

_state: dict[str, FusionServer | None] = {"server": None}


def start() -> None:
    try:
        server = FusionServer()
        _state["server"] = server
        server.start()
    except Exception:
        futil.handle_error("server_start")


def stop() -> None:
    try:
        server = _state["server"]
        if server:
            server.stop()
    except Exception:
        futil.handle_error("server_stop")
