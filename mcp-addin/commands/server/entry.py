from ...lib import fusionAddInUtils as futil
from .server import FusionServer

_server = None


def start():
    try:
        global _server
        _server = FusionServer()
        _server.start()
    except Exception:
        futil.handle_error("server_start")


def stop():
    try:
        global _server
        if _server:
            _server.stop()
    except Exception:
        futil.handle_error("server_stop")
