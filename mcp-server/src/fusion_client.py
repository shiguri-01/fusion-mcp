import logging
from dataclasses import dataclass
from typing import Any

import httpx

# ログ設定
logging.basicConfig(level=logging.INFO)
logger = logging.getLogger("Fusion MCP Server")

# 定数
DEFAULT_HOST = "localhost"
DEFAULT_PORT = 3600
DEFAULT_TIMEOUT = 10.0

ADDIN_CONNECTION_ERROR = {
    "type": "FusionServerConnectionError",
    "message": "Cannot connect to 'mcp-addin', Fusion Add-in. Instruct the user to run 'mcp-addin'.",
}

ADDIN_TIMEOUT_ERROR = {
    "type": "FusionServerTimeoutError",
    "message": "Fusion took too long to respond. The operation may be complex or Fusion may be busy.  Break complex operations into smaller steps.",
}

RESPONSE_PARSE_ERROR = {
    "type": "FusionServerResponseError",
    "message": "Received invalid response from Fusion. This may indicate a compatibility issue. Instruct the user to check 'Fusion MCP' is up to date.",
}

UNKNOWN_ERROR = {
    "type": "UnknownError",
    "message": "An unexpected error occurred in the MCP server. Check the server logs for details.",
}


def format_error(
    error_type: str | None = None,
    message: str | None = None,
) -> str:
    if error_type is None:
        error_type = UNKNOWN_ERROR["type"]
    if message is None:
        message = UNKNOWN_ERROR["message"]

    return f"{error_type}: {message}"


@dataclass
class FusionAddinClient:
    """Fusionアドインのサーバーと接続するクライアント"""

    host: str = DEFAULT_HOST
    port: int = DEFAULT_PORT

    @property
    def base_url(self) -> str:
        """サーバーのベースURL"""
        return f"http://{self.host}:{self.port}"

    async def call_action(
        self,
        action_name: str,
        params: dict[str, Any] | None = None,
    ) -> dict[str, Any]:
        """アドインサーバーのアクションを呼び出す

        Args:
            action_name (str): 呼び出すアクション名
            params (dict, optional): アクションのパラメータ

        Returns:
            dict: アクションの実行結果

        """
        url = f"{self.base_url}/{action_name}"
        params = params or {}

        logger.info(f"Calling action '{action_name}' at {url}")

        try:
            async with httpx.AsyncClient(timeout=DEFAULT_TIMEOUT) as client:
                response = await client.post(url, json=params)

            # JSONレスポンスをデコード
            try:
                response_data = response.json()
            except Exception:
                logger.exception(f"Failed to decode JSON response from {url}: {response.text}")
                return self._create_error_response(
                    RESPONSE_PARSE_ERROR["type"],
                    RESPONSE_PARSE_ERROR["message"],
                )

            # レスポンス処理
            if response.is_success:
                return self._handle_ok_response(response_data, action_name)

            return self._handle_error_response(response_data, response.status_code, action_name)

        except httpx.ConnectError:
            logger.exception(f"Connection to {url} failed. Is the server running?")
            return self._create_error_response(
                ADDIN_CONNECTION_ERROR["type"],
                ADDIN_CONNECTION_ERROR["message"],
            )

        except httpx.TimeoutException:
            logger.exception(f"Request to {url} timed out.")
            return self._create_error_response(
                ADDIN_TIMEOUT_ERROR["type"],
                ADDIN_TIMEOUT_ERROR["message"],
            )

        except httpx.RequestError as e:
            logger.exception(f"Request failed: {e!s}")
            return self._create_error_response(
                "FusionServerRequestError",
                f"Network error while communicating with Fusion Add-in: {e!s}. Please ask the user to check their network connection and ensure Fusion is accessible.",
            )

        except Exception as e:
            logger.exception(f"Unexpected error while calling action '{action_name}': {e!s}")
            return self._create_error_response(
                UNKNOWN_ERROR["type"],
                f"{UNKNOWN_ERROR['message']} Details: {e!s}",
            )

    def _handle_ok_response(
        self,
        response_data: dict[str, Any],
        action_name: str,
    ) -> dict[str, Any]:
        """HTTPステータスが正常な場合のレスポンス処理"""
        is_success = response_data.get("success", False)

        if is_success:
            return response_data

        # サーバーからの論理エラー
        logger.error(f"Action '{action_name}' failed with error: {response_data.get('error', {})}")

        error_info = response_data.get("error", {})
        return self._create_error_response(
            error_info.get("type", "FusionServerError"),
            error_info.get("message", "An unknown error occurred"),
        )

    def _handle_error_response(
        self,
        response_data: dict[str, Any],
        status_code: int,
        action_name: str,
    ) -> dict[str, Any]:
        """HTTPエラーステータスの場合のレスポンス処理"""
        logger.error(
            f"Action '{action_name}' failed with HTTP status {status_code}: {response_data}",
        )
        error_info = response_data.get("error", {})
        return self._create_error_response(
            error_info.get("type", "ServerError"),
            error_info.get("message", f"Server returned status {status_code}"),
        )

    def _create_error_response(self, error_type: str, message: str) -> dict[str, Any]:
        """エラーレスポンスを作成する"""
        return {
            "success": False,
            "error": {
                "type": error_type,
                "message": message,
            },
        }
