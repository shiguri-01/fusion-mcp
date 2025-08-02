from typing import TypedDict

import adsk.core
import adsk.fusion
from adsk.fusion import Parameter

from ..errors import FusionExecutionError, InvalidUserInputError


class FusionParameter(TypedDict):
    name: str
    value: float
    unit: str
    expression: str
    comment: str


def parameter_to_dict(param: Parameter) -> FusionParameter:
    """パラメータを辞書形式に変換する

    Args:
        param (Parameter): Fusionのパラメータオブジェクト

    Returns:
        dict: パラメータの情報を含む辞書

    """
    param_dict: FusionParameter = {
        "name": param.name,
        "value": param.value,
        "unit": param.unit,
        "expression": param.expression,
        "comment": param.comment or "",
    }
    return param_dict


def get_user_parameters() -> list[FusionParameter]:
    """ユーザーパラメータの一覧を取得する

    Returns:
        list[dict]: ユーザーパラメータのリスト

    """
    app = adsk.core.Application.get()
    if not app.activeProduct:
        raise FusionExecutionError("No active design found")

    design = adsk.fusion.Design.cast(app.activeProduct)
    if not design:
        raise FusionExecutionError("Active product is not a design")

    user_params = design.userParameters.asArray()
    return [parameter_to_dict(param) for param in user_params]


def set_parameter(param_name: str, expression: str) -> FusionParameter:
    """指定したパラメータの値を設定する

    ユーザーパラメータ・モデルパラメータの両方に対応

    Args:
        param_name (str): 設定するパラメータの名前
        expression (str): 設定する値の式（例: "10 cm"）

    Returns:
        dict: 設定後のパラメータ情報

    Raises:
        InvalidUserInputError: 入力が不正な場合
        FusionExecutionError: パラメータの設定に失敗した場合

    """
    if not param_name:
        raise InvalidUserInputError("Parameter 'param_name' cannot be empty")
    if not expression:
        raise InvalidUserInputError("Parameter 'expression' cannot be empty")

    app = adsk.core.Application.get()
    if not app.activeProduct:
        raise FusionExecutionError("No active design found")

    design = adsk.fusion.Design.cast(app.activeProduct)
    if not design:
        raise FusionExecutionError("Active product is not a design")

    parameter = design.allParameters.itemByName(param_name)
    if not parameter:
        raise FusionExecutionError(f"Parameter '{param_name}' not found")

    try:
        parameter.expression = expression
        return parameter_to_dict(parameter)
    except Exception as e:
        raise FusionExecutionError(f"Failed to set parameter '{param_name}': {e}") from e
