import adsk.core

from ..errors import FusionExecutionError, InvalidUserInputError


def get_viewport_screenshot(filepath: str | None = None) -> dict[str, str]:
    """ビューポートのスクリーンショットを撮り、指定されたパスに保存する

    Args:
        filepath (str): スクリーンショット保存するファイルのパス。

    Raises:
        InvalidUserInputError: filepathがNoneや未指定の場合に発生
        FusionExecutionError:
            ビューポートが見つからない場合や、スクリーンショットの保存に失敗した場合に発生

    Returns:
        dict:
            - "filepath": 保存されたファイルのパス

    """
    if not filepath:
        raise InvalidUserInputError("Parameter 'filepath' cannot be empty")

    app = adsk.core.Application.get()
    viewport = app.activeViewport

    if not viewport:
        raise FusionExecutionError("No active viewport found. Cannot take screenshot.")

    # ビューポートの画像を保存
    # 0, 0でビューポートの画面上のサイズと同じサイズの画像を保存
    success = viewport.saveAsImageFile(filepath, 0, 0)

    if not success:
        raise FusionExecutionError(f"Failed to save screenshot to {filepath}")

    return {"filepath": filepath}
