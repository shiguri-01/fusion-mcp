import json
import threading
from http.server import BaseHTTPRequestHandler, HTTPServer
from typing import Any

from ...lib import fusionAddInUtils as futil
from .errors import FusionExecutionError, FusionServerError, InvalidUserInputError
from .handlers import execute_code


class FusionServer:
    """FusionアドインでMCPサーバーからのリクエストを受け付けるサーバー"""

    def __init__(self, host: str = "localhost", port: int = 3600) -> None:
        """FusionServerの初期化

        Args:
            host (str): サーバーのホスト名またはIPアドレス
            port (int): サーバーのポート番号

        """
        self.host = host
        self.port = port

        self.is_running = False

        self.http_server = None
        self.server_thread: threading.Thread | None = None

        self.actions = {
            "execute_code": execute_code.execute_code_in_transaction,
        }

    def _create_handler_class(self) -> type[BaseHTTPRequestHandler]:
        # self(FusionServerインスタンス)をハンドラーから参照できるようにする
        server_instance = self

        class CustomHandler(BaseHTTPRequestHandler):
            def do_POST(self) -> None:
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
                    result = server_instance._execute_handler(action_name, **params)  # noqa: SLF001

                    response_data = {
                        "success": True,
                        "result": result,
                    }
                    status_code = 200

                except FusionExecutionError as e:
                    # 意図的に分類されたエラー
                    futil.handle_error(f"Action failed: [{e.error_type}] {e}")
                    response_data = {
                        "success": False,
                        "error": {
                            "type": e.error_type,
                            "message": str(e),
                        },
                    }
                    status_code = 400 if isinstance(e, InvalidUserInputError) else 500

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
                    self.send_response(status_code)
                    self.send_header("Content-Type", "application/json")
                    self.end_headers()
                    self.wfile.write(json.dumps(response_data).encode("utf-8"))

            def log_message(self, format: str, *args: Any) -> None:  # noqa: A002, ANN401
                # HTTPサーバーのログメッセージを無効化
                pass

        return CustomHandler

    def start(self) -> None:
        if self.is_running:
            futil.log("FusionServer is already running.")
            return

        try:
            handler = self._create_handler_class()
            self.http_server = HTTPServer((self.host, self.port), handler)

            self.is_running = True

            self.server_thread = threading.Thread(target=self.http_server.serve_forever)
            self.server_thread.daemon = True
            self.server_thread.start()

            futil.log(f"FusionServer started on {self.host}:{self.port}")

        except Exception as e:
            futil.handle_error(f"Failed to start FusionServer.\n\n{e}", show_message_box=True)
            self.stop()

    def stop(self) -> None:
        if self.http_server and self.is_running:
            futil.log("Stopping FusionServer...")

            self.http_server.shutdown()  # スレッド内のループを止める
            self.http_server.server_close()  # ソケットを閉じる

            self.is_running = False
            self.http_server = None

            futil.log("FusionServer stopped.")
        else:
            futil.log("FusionServer is not running or already stopped.")
            self.is_running = False  # 念のため

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
