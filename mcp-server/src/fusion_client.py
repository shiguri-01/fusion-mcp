import logging
from dataclasses import dataclass
from typing import Any

import httpx

# ログ設定
logging.basicConfig(level=logging.INFO)
logger = logging.getLogger("Fusion MCP Server")

# 定数
DEFAULT_HOST = "127.0.0.1"
DEFAULT_PORT = 3600
DEFAULT_TIMEOUT = 10.0
HTTP_STATUS_FORBIDDEN = 403

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

ACCESS_DENIED_ERROR = {
    "type": "FusionServerAccessDeniedError",
    "message": "Fusion add-in rejected a non-local request. Ensure mcp-server runs on the same machine as Fusion.",
}


class FusionHealthCheckError(Exception):
    """Raised when a health check cannot determine connectivity."""

    def __init__(self, error_type: str, message: str) -> None:
        super().__init__(message)
        self.error_type = error_type
        self.message = message


def format_error(
    error_type: str | None = None,
    message: str | None = None,
) -> str:
    """Format an MCP error type and message for logging or display."""
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

    async def check_health(self) -> dict[str, Any]:
        """Fusion add-in への接続状態を確認する.

        Returns:
            dict: 接続状態。未接続は正常な判定結果として返す。

        Raises:
            FusionHealthCheckError: 接続状態を判定できない場合

        """
        url = f"{self.base_url}/health"
        logger.info(f"Checking Fusion add-in health at {url}")

        try:
            async with httpx.AsyncClient(timeout=DEFAULT_TIMEOUT) as client:
                response = await client.post(url, json={})
        except httpx.ConnectError:
            logger.info(f"Fusion add-in is not reachable at {url}")
            return {
                "connected": False,
                "service": "mcp-addin",
                "message": (
                    "Fusion add-in is not reachable. Ask the user to start 'mcp-addin' in Fusion."
                ),
            }
        except httpx.TimeoutException as e:
            logger.exception(f"Health check to {url} timed out.")
            raise FusionHealthCheckError(
                ADDIN_TIMEOUT_ERROR["type"],
                ADDIN_TIMEOUT_ERROR["message"],
            ) from e
        except httpx.RequestError as e:
            logger.exception(f"Health check request failed: {e!s}")
            raise FusionHealthCheckError(
                "FusionServerRequestError",
                f"Network error while communicating with Fusion Add-in: {e!s}.",
            ) from e

        try:
            response_data = response.json()
        except Exception as e:
            logger.exception(f"Failed to decode JSON response from {url}: {response.text}")
            raise FusionHealthCheckError(
                RESPONSE_PARSE_ERROR["type"],
                RESPONSE_PARSE_ERROR["message"],
            ) from e

        if not response.is_success:
            if response.status_code == HTTP_STATUS_FORBIDDEN:
                raise FusionHealthCheckError(
                    ACCESS_DENIED_ERROR["type"],
                    ACCESS_DENIED_ERROR["message"],
                )
            logger.error(
                "Health check failed with HTTP status %s: %s",
                response.status_code,
                response_data,
            )
            raise FusionHealthCheckError(
                "FusionHealthCheckError",
                f"Health check returned unexpected HTTP status {response.status_code}.",
            )

        if not response_data.get("success", False):
            error_info = response_data.get("error", {})
            raise FusionHealthCheckError(
                error_info.get("type", "FusionHealthCheckError"),
                error_info.get("message", "Fusion add-in health check did not return success."),
            )

        result = response_data.get("result", {})
        return {
            "connected": True,
            "service": result.get("service", "mcp-addin"),
            "message": "Fusion add-in is reachable.",
        }

    async def call_action(  # noqa: PLR0911
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
        if status_code == HTTP_STATUS_FORBIDDEN:
            return self._create_error_response(
                ACCESS_DENIED_ERROR["type"],
                ACCESS_DENIED_ERROR["message"],
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
