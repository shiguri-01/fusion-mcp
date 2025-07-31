import logging
import os
import tempfile
from dataclasses import dataclass
from pathlib import Path
from typing import Annotated, Any

import requests
from fastmcp import Context, FastMCP
from fastmcp.utilities.types import Image
from pydantic import Field

# ログ設定
logging.basicConfig(level=logging.INFO)
logger = logging.getLogger("Fusion360 MCP Server")

# 定数
DEFAULT_HOST = "localhost"
DEFAULT_PORT = 3600
DEFAULT_TIMEOUT = 10.0

ADDIN_CONNECTION_ERROR_RESPONSE = {
    "error": {
        "type": "FusionServerConnectionError",
        "message": "Connection to the Fusion Add-in `mcp-addin` failed. Ask the user to check if the add-in is running.",
    },
}
UNKNOWN_ERROR_RESPONSE = {
    "error": {
        "type": "UnknownError",
        "message": "An unknown error occurred.",
    },
}


@dataclass
class FusionAddinClient:
    """Fusionアドインのサーバーと接続するクライアント"""

    host: str = DEFAULT_HOST
    port: int = DEFAULT_PORT

    @property
    def base_url(self) -> str:
        """サーバーのベースURL"""
        return f"http://{self.host}:{self.port}"

    def call_action(self, action_name: str, params: dict[str, Any] | None) -> dict[str, Any]:
        """アドインサーバーのアクションを呼び出す

        Args:
            action_name (str): 呼び出すアクション名
            params (dict, optional): アクションのパラメータ

        Returns:
            dict: アクションの実行結果

        Raises:
            ConnectionError: サーバーへの接続に失敗した場合やタイムアウトした場合
            Exception: アドインサーバー側のエラーや、その他のリクエストエラー

        """
        url = f"{self.base_url}/{action_name}"
        if params is None:
            params = {}

        logger.info(f"Calling action '{action_name}' at {url}")

        try:
            response = requests.post(url, json=params, timeout=DEFAULT_TIMEOUT)

            response_data = response.json()

            success = response_data.get("success", False) and response.status_code == 200

            if success:
                return response_data

            error_info = response_data.get("error", {})
            return {
                success: False,
                "error": {
                    "type": error_info.get("type", "UnknownError"),
                    "message": error_info.get("message", "An unknown error occurred"),
                },
            }

        except requests.ConnectionError:
            logger.exception(f"Connection to {url} failed. Is the server running?")
            return {
                "success": False,
                **ADDIN_CONNECTION_ERROR_RESPONSE,
            }
        except requests.Timeout:
            logger.exception(f"Request to {url} timed out.")
            return {
                "success": False,
                "error": {
                    "type": "ServerTimeoutError",
                    "message": f"Request timed out after {DEFAULT_TIMEOUT} seconds",
                },
            }
        except requests.RequestException as e:
            logger.exception(f"Request failed: {e}")
            return {
                "success": False,
                "error": {
                    "type": "ServerRequestError",
                    "message": f"An error occurred while making the request to Fusion: {e!s}",
                },
            }
        except Exception as e:
            # その他の予期しないエラー
            logger.exception(f"Unexpected error while calling action '{action_name}': {e}")
            return {
                "success": False,
                **UNKNOWN_ERROR_RESPONSE,
            }


_fusion_addin_client: FusionAddinClient | None = None


def get_fusion_addin_client() -> FusionAddinClient:
    """FusionAddinClientのシングルトンインスタンスを取得する"""
    global _fusion_addin_client
    if _fusion_addin_client is None:
        _fusion_addin_client = FusionAddinClient()
    return _fusion_addin_client


# FastMCP サーバーインスタンス
mcp = FastMCP(
    "Fusion MCP Server",
    instructions="""MCP server that enables AI agents to perform CAD operations in Autodesk Fusion.
Provides tools for 3D modeling, sketching, assemblies, simulations, and design automation through the Fusion API.""",
)


@mcp.tool
async def execute_code(
    ctx: Context,
    code: Annotated[
        str,
        Field(
            description="""Python script to execute in Fusion.
            Has access to Fusion API objects.
            Must be syntactically valid Python code.
            Use 'print()' statements to capture output.""",
            min_length=1,
            max_length=20000,
        ),
    ],
    summary: Annotated[
        str | None,
        Field(
            description="Optional summary of the code being executed",
            max_length=1000,
            default=None,
        ),
    ] = None,
) -> str | dict[str, str]:
    """Execute a Python script as a single transaction in Autodesk Fusion 360.

    This tool runs Python code with access to the Fusion 360 API. Any modifications
    to the CAD model are grouped into a single transaction, which can be undone in
    Fusion's UI. If the code performs no modifications (e.g., only uses `print`),
    no transaction is recorded.

    **Return Value:**
    The tool's return value depends on whether the tool itself executed successfully,
    not on whether the provided code ran without errors.

    - **On SUCCESS (returns `str`):**
      - The captured output from `print()` statements.
      - If the user's code has an error, the Python stack trace is returned as part
        of this string. This is still considered a successful tool execution.

    - **On FAILURE (returns `dict`):**
      - A dictionary `{"error": {"type": "...", "message": "..."}}` is returned
        if the tool fails internally (e.g., cannot connect to Fusion).

    **Execution Context:**
    The script has access to pre-initialized Fusion API objects:
    - `adsk`: The root API module.
    - `app`: The application instance.
    - `design`: The active design document.
    - `root_comp`: The root component of the design.
    """
    execution_result: str = ""
    try:
        connection = get_fusion_addin_client()

        result = connection.call_action(
            "execute_code",
            {"code": code, "transaction_name": summary},
        )

        if not result.get("success", False):
            return {"error": result.get("error", {})}

        execution_result = result.get("result", "")

    except ConnectionError:
        return ADDIN_CONNECTION_ERROR_RESPONSE

    except Exception as e:
        error_msg = f"Code execution failed: {e!s}"
        return {"error": {"type": "UnknownError", "message": error_msg}}

    else:
        return execution_result


@mcp.tool
def get_viewport_screenshot() -> Image | dict[str, str]:
    """Capture a screenshot of the current Fusion viewport.

    The screenshot shows exactly what the user sees in their Fusion viewport,
    including the current view angle, zoom level, and any active UI elements.
    This is particularly useful after executing modeling code to confirm the
    expected visual results.

    **Use this tool to:**
    - Visualize the current state of the 3D model for analysis or documentation
    - Verify the results of CAD operations or design changes
    - Help users understand what's currently displayed in Fusion
    - Create visual references for design reviews or troubleshooting
    - Capture the viewport when providing visual feedback about modeling operations

    **Return Value:**
    Returns an Image object containing the viewport screenshot as PNG data.
    """
    try:
        connection = get_fusion_addin_client()

        temp_dir = Path(tempfile.gettempdir())
        filename = f"fusion_viewport_screenshot_{os.getpid()}.png"
        filepath = temp_dir / filename

        result = connection.call_action("get_viewport_screenshot", {"filepath": str(filepath)})

        if not result.get("success", False):
            return {"error": result.get("error", {})}

        if not Path.exists(filepath):
            return {
                "error": {
                    "type": "FileNotFoundError",
                    "message": f"Screenshot file not found at {filepath}",
                },
            }

        with Path.open(filepath, "rb") as f:
            image_bytes = f.read()

        Path(filepath).unlink(missing_ok=True)
        return Image(data=image_bytes)

    except ConnectionError:
        return ADDIN_CONNECTION_ERROR_RESPONSE
    except Exception as e:
        error_msg = f"Failed to get viewport screenshot: {e!s}"
        return {"error": {"type": "UnknownError", "message": error_msg}}


def main() -> None:
    mcp.run()


if __name__ == "__main__":
    main()
