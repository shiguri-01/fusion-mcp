import io
from contextlib import redirect_stdout

import adsk.cam
import adsk.core
import adsk.fusion

from ..errors import FusionExecutionError, InvalidUserInputError


def execute_code(code: str, description: str = "Python Script Execution") -> str:
    """任意のPythonスクリプトを実行する

    Args:
        code (str): 実行するPythonコード
        description (str): スクリプトの説明（デフォルトは "Python Script Execution"）

    Returns:
        str: 実行結果の文字列。標準出力の内容が含まれる

    """
    if not code:
        raise InvalidUserInputError("Parameter 'code' cannot be empty for action 'execute_code'")

    try:
        app = adsk.core.Application.get()
        design = adsk.fusion.Design.cast(app.activeProduct)

        root_comp = design.rootComponent if design else None

        # スクリプト実行用のローカル名前空間を準備
        namespace = {
            "adsk.core": adsk.core,
            "adsk.fusion": adsk.fusion,
            "adsk.cam": adsk.cam,
            "app": app,
            "design": design,
            "root_comp": root_comp,
        }

        # 実行中の出力をキャプチャし、実行結果として返す
        capture_buffer = io.StringIO()
        with redirect_stdout(capture_buffer):
            exec(code, namespace)

        captured_output = capture_buffer.getvalue()

    except Exception as e:
        raise FusionExecutionError(f"Code execution error: {e!s}") from e
    else:
        return captured_output
