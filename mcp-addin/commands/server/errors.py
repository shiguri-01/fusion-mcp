class FusionServerError(Exception):
    """FusionServerで発生するエラーの基底クラス

    ユーザー（AIエージェントなど）がエラーの詳細を理解できるようにするためのカスタム例外
    エラー原因がFusionServer自体でなくても、ユーザーに向けたレスポンスにはこの例外を使用する
    """

    def __init__(self, message: str, error_type: str = "UnknownError") -> None:
        super().__init__(message)
        self.error_type = error_type


class InvalidUserInputError(FusionServerError):
    """ユーザーの入力が無効な場合に発生するエラー"""

    def __init__(self, message: str) -> None:
        super().__init__(message, error_type="InvalidUserInput")


class FusionExecutionError(FusionServerError):
    """Fusion APIのコード実行中に発生するエラー"""

    def __init__(self, action_name: str, message: str) -> None:
        super().__init__(
            f"Error executing action '{action_name}': {message}",
            error_type="FusionExecutionError",
        )
        self.action_name = action_name


class ServerConnectionError(FusionServerError):
    """サーバーへの接続に失敗した場合に発生するエラー"""

    def __init__(self, message: str) -> None:
        super().__init__(message, error_type="ServerConnectionError")


class ServerError(FusionServerError):
    """FusionServer内部の予期しないエラー"""

    def __init__(self, message: str) -> None:
        super().__init__(message, error_type="ServerError")
