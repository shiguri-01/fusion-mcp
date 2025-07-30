import logging
from dataclasses import dataclass
from typing import Annotated, Any

import requests
from fastmcp import Context, FastMCP
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
    description: Annotated[
        str | None,
        Field(
            description="Optional description of the code being executed",
            max_length=1000,
            default=None,
        ),
    ] = None,
) -> dict[str, Any]:
    """Execute Python code within Autodesk Fusion CAD environment.

    Provides full access to the Fusion API for 3D modeling, sketching, assemblies,
    simulations, and data extraction. Code executes in the active Fusion design
    with pre-initialized objects: adsk, app, design, rootComp.

    Print statements are captured and returned as output. Operations are applied
    immediately to the CAD model - use Fusion's undo to revert changes.

    Available objects in execution namespace:
    - adsk: Complete Fusion API module (adsk.core, adsk.fusion, adsk.cam)
    - app: Application instance (adsk.core.Application.get())
    - design: Current active design document
    - root_comp: Root component of the current design

    Returns:
        JSON string with execution results: {"result": "output"} or {"error": "msg"}

    """
    try:
        connection = get_fusion_addin_client()

        result = connection.call_action("execute_code", {"code": code})

        if not result.get("success", False):
            return {"error": result.get("error", {})}

        return {"result": result.get("result", "")}

    except ConnectionError:
        return ADDIN_CONNECTION_ERROR_RESPONSE

    except Exception as e:
        error_msg = f"Code execution failed: {e!s}"
        return {"error": {"type": "UnknownError", "message": error_msg}}
    else:
        return result


def main() -> None:
    mcp.run()


if __name__ == "__main__":
    main()
