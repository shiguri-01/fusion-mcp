import os
import tempfile
from collections.abc import Callable
from functools import wraps
from pathlib import Path
from typing import Annotated

import httpx
from fastmcp import Context, FastMCP
from fastmcp.exceptions import ToolError
from fastmcp.utilities.types import Image
from fusion_client import (
    ADDIN_CONNECTION_ERROR,
    ADDIN_TIMEOUT_ERROR,
    RESPONSE_PARSE_ERROR,
    UNKNOWN_ERROR,
    FusionAddinClient,
    format_error,
)
from pydantic import Field, ValidationError

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


def handle_tool_error[**P, R](tool_func: Callable[P, R]) -> Callable[P, R]:
    """MCPツールのエラーハンドリングをおこなうデコレータ"""

    @wraps(tool_func)
    async def wrapper(*args: P.args, **kwargs: P.kwargs) -> R:
        try:
            return await tool_func(*args, **kwargs)

        except ToolError:
            # ToolErrorはそのまま再スロー
            raise

        except httpx.ConnectError as e:
            raise ToolError(
                format_error(ADDIN_CONNECTION_ERROR["type"], ADDIN_CONNECTION_ERROR["message"]),
            ) from e
        except httpx.TimeoutException as e:
            raise ToolError(
                format_error(
                    ADDIN_TIMEOUT_ERROR["type"],
                    ADDIN_TIMEOUT_ERROR["message"],
                ),
            ) from e
        except ValidationError as e:
            raise ToolError(
                format_error(
                    RESPONSE_PARSE_ERROR["type"],
                    RESPONSE_PARSE_ERROR["message"],
                ),
            ) from e
        except Exception as e:
            func_name = getattr(tool_func, "__name__", "tool")
            error_msg = f"Failed to execute {func_name}: {e!s}"
            raise ToolError(format_error(UNKNOWN_ERROR["type"], error_msg)) from e

    return wrapper


@mcp.tool
@handle_tool_error
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
            max_length=100,
            default=None,
        ),
    ] = None,
) -> str:
    """Execute Python code in Autodesk Fusion with full API access.

    - Create, modify, and analyze CAD models.
    - Group all model changes into a single, undoable transaction.

    Pre-initialized objects:
    - `adsk`: The root API module.
    - `app`: The application instance.
    - `design`: The active design document.
    - `root_comp`: The root component of the design.

    Returns:
    All `print()` output as string, including error tracebacks if execution fails.

    Important:
    - The environment is reset for each execution.
      Include all required imports and variables every time.
    - Always use `print()` to show progress and results.

    """
    connection = get_fusion_addin_client()

    result = await connection.call_action(
        "execute_code",
        {"code": code, "transaction_name": summary},
    )

    if not result.get("success", False):
        error_info = result.get("error", {})
        error_type = error_info.get("type", "UnknownError")
        error_msg = error_info.get("message", "An unknown error occurred")
        raise ToolError(format_error(error_type, error_msg))

    output: str = result.get("result", "")
    return output


@mcp.tool
@handle_tool_error
async def get_viewport_screenshot() -> Image:
    """Capture a screenshot of the current Fusion viewport.

    - Captures the viewport's current visual state, including the camera's perspective, orientation, and zoom.
    - Ideal for verifying modeling results, documenting the design state,
      or providing visual feedback after a script runs.

    Returns:
    Image object with screenshot data.

    """
    connection = get_fusion_addin_client()

    # 一時ファイルを作成してスクリーンショットを保存
    fd, filepath_str = tempfile.mkstemp(prefix="fusion_viewport_screenshot_", suffix=".png")
    os.close(fd)  # パスだけ必要なので、ファイルディスクリプタは閉じる
    filepath = Path(filepath_str)

    try:
        result = await connection.call_action(
            "get_viewport_screenshot",
            {"filepath": str(filepath)},
        )

        if not result.get("success", False):
            error_info = result.get("error", {})
            error_type = error_info.get("type", "UnknownError")
            error_msg = error_info.get("message", "An unknown error occurred")
            raise ToolError(format_error(error_type, error_msg))

        if not Path.exists(filepath):
            raise ToolError(
                format_error(
                    "FusionScreenshotError",
                    f"Screenshot was not created by Fusion Add-in. This may indicate a permission issue or Fusion internal error. Please ask the user to check Fusion's file access permissions and try again. Expected file: {filepath}",
                ),
            )

        with Path.open(filepath, "rb") as f:
            image_bytes = f.read()

        return Image(data=image_bytes)
    finally:
        # 一時ファイルを削除
        Path(filepath).unlink(missing_ok=True)


def main() -> None:
    mcp.run()


if __name__ == "__main__":
    main()
