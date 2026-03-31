import json
import socket
import threading
from http.server import BaseHTTPRequestHandler, HTTPServer
from ipaddress import ip_address
from typing import Any

from ...lib import fusionAddInUtils as futil
from .errors import FusionExecutionError, FusionServerError, InvalidUserInputError
from .handlers import execute_code, health, parameters, screenshot


class FusionServer:
    """FusionアドインでMCPサーバーからのリクエストを受け付けるサーバー"""

    def __init__(self, port: int = 3600) -> None:
        """FusionServerの初期化

        Args:
            port (int): サーバーのポート番号

        """
        self.port = port

        self.is_running = False

        self.http_servers: list[HTTPServer] = []
        self.server_threads: list[threading.Thread] = []

        self.actions = {
            "health": health.health,
            "execute_code": execute_code.execute_code_in_transaction,
            "get_viewport_screenshot": screenshot.get_viewport_screenshot,
            # parameters
            "get_user_parameters": parameters.get_user_parameters,
            "set_parameter": parameters.set_parameter,
        }

    def _create_handler_class(self) -> type[BaseHTTPRequestHandler]:
        """Create an HTTP handler bound to this server instance."""
        # self(FusionServerインスタンス)をハンドラーから参照できるようにする
        server_instance = self

        class CustomHandler(BaseHTTPRequestHandler):
            def do_POST(self) -> None:
                client_ip = self.client_address[0]
                if not is_loopback_address(client_ip):
                    futil.log(f"Rejected non-local request from {client_ip}")
                    self._send_json_response(
                        403,
                        {
                            "success": False,
                            "error": {
                                "type": "Forbidden",
                                "message": "Only local loopback requests are allowed.",
                            },
                        },
                    )
                    return

                response_data: dict[str, Any] = {}
                status_code = 500

                try:
                    # URLパスからアクション名を取得
                    action_name = self.path.strip("/")

                    # リクエストボディを読み込む
                    content_length = int(self.headers.get("Content-Length", 0))
                    post_data = self.rfile.read(content_length).decode("utf-8")
                    params = json.loads(post_data) if post_data else {}

                    # アクションを実行
                    # FusionServerErrorが発生する可能性がある
                    result = server_instance._execute_handler(action_name, **params)

                    response_data = {
                        "success": True,
                        "result": result,
                    }
                    status_code = 200

                except FusionServerError as e:
                    # 意図的に分類されたエラー
                    # アプリレベルのエラーなのでsuccessフィールドをFalseにして、
                    # HTTPステータスコードは200を返す
                    futil.handle_error(f"Action failed: [{e.error_type}] {e}")
                    response_data = {
                        "success": False,
                        "error": {
                            "type": e.error_type,
                            "message": str(e),
                        },
                    }
                    status_code = 200

                except json.JSONDecodeError as e:
                    futil.handle_error(f"Invalid JSON in request: {e}")
                    response_data = {
                        "success": False,
                        "error": {"type": "BadRequest", "message": f"Invalid JSON format: {e}"},
                    }
                    status_code = 400

                except Exception as e:
                    futil.handle_error(f"Unexpected error processing request: {e}")
                    response_data = {
                        "success": False,
                        "error": {
                            "type": "InternalServerError",
                            "message": f"An unexpected internal error occurred: {e}",
                        },
                    }
                    status_code = 500

                finally:
                    self._send_json_response(status_code, response_data)

            def _send_json_response(self, status_code: int, response_data: dict[str, Any]) -> None:
                self.send_response(status_code)
                self.send_header("Content-Type", "application/json")
                self.end_headers()
                self.wfile.write(json.dumps(response_data).encode("utf-8"))

            def log_message(self, format: str, *args: Any) -> None:  # noqa: A002, ANN401
                # HTTPサーバーのログメッセージを無効化
                pass

        return CustomHandler

    def start(self) -> None:
        """Start IPv4/IPv6 loopback listeners for the Fusion add-in server."""
        if self.is_running:
            futil.log("FusionServer is already running.")
            return

        try:
            handler = self._create_handler_class()
            self.http_servers = [
                self._create_http_server("127.0.0.1", handler),
            ]

            try:
                self.http_servers.append(self._create_http_server("::1", handler))
            except OSError as e:
                futil.log(f"IPv6 loopback listener is unavailable: {e}")

            self.server_threads = []
            for http_server in self.http_servers:
                thread = threading.Thread(target=http_server.serve_forever)
                thread.daemon = True
                thread.start()
                self.server_threads.append(thread)

            self.is_running = True
            futil.log(
                f"FusionServer started on loopback only: 127.0.0.1:{self.port}"
                + (f", [::1]:{self.port}" if len(self.http_servers) > 1 else ""),
            )

        except Exception as e:
            futil.handle_error(f"Failed to start FusionServer.\n\n{e}")
            self.stop()

    def stop(self) -> None:
        """Stop all active HTTP listeners and background server threads."""
        if self.http_servers:
            futil.log("Stopping FusionServer...")

            for http_server in self.http_servers:
                http_server.shutdown()
                http_server.server_close()

            for thread in self.server_threads:
                thread.join(timeout=1)

            self.is_running = False
            self.http_servers = []
            self.server_threads = []

            futil.log("FusionServer stopped.")
        else:
            futil.log("FusionServer is not running or already stopped.")
            self.is_running = False  # 念のため

    def _create_http_server(
        self,
        host: str,
        handler: type[BaseHTTPRequestHandler],
    ) -> HTTPServer:
        if ":" in host:

            class IPv6HTTPServer(HTTPServer):
                address_family = socket.AF_INET6

            return IPv6HTTPServer((host, self.port), handler)

        return HTTPServer((host, self.port), handler)

    def _execute_handler(self, action_name: str, **params: object) -> object:
        """指定されたアクションのハンドラーを実行する

        CustomHandlerインスタンスから呼び出される。
        CustomHandlerはselfの中で作成されるため、プライベートメソッドとして定義。

        Args:
            action_name (str): 実行するアクションの名前
            **params: アクションに渡すパラメータ

        Returns:
            object: アクションの実行結果

        Raises:
            FusionServerError: アクションの実行中にエラーが発生した場合


        """
        if action_name not in self.actions:
            raise InvalidUserInputError(f"Action '{action_name}' not found.")

        try:
            handler_method = self.actions[action_name]
            result = handler_method(**params)

        except FusionServerError:
            # このサーバー用に定義されたエラー
            # そのまま返す
            raise
        except Exception as e:
            raise FusionExecutionError(
                f"An error occurred during execution in Fusion 360: {e}",
            ) from e

        else:
            return result


def is_loopback_address(address: str) -> bool:
    """Return True when the client address is a loopback IPv4 or IPv6 address."""
    try:
        return ip_address(address).is_loopback
    except ValueError:
        return False
