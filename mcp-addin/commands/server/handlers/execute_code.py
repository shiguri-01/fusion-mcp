import io
import traceback
import uuid
from dataclasses import dataclass
from typing import Any

import adsk
import adsk.cam
import adsk.core
import adsk.fusion

from ....lib import fusionAddInUtils as futil
from ..errors import FusionExecutionError, InvalidUserInputError


@dataclass
class CommandExecutionState:
    """コード実行コマンド内部の情報を保持するためのコンテナ

    コードの実行を1つのトランザクションにまとめるためにcommandを使用する。
    commandは非同期で実行され値を返却できないため、このコンテナでデータを保存する。
    """

    code_result: str | None = None
    """コードの実行結果

    標準入出力・コード内でのエラーのトレースバック"""

    fusion_error: Exception | None = None
    """Fusionのコマンド側で発生したエラー

    渡されたコードで発生したエラーはoutputに保存される。
    """

    is_finished: bool = False


class CommandExecuteHandler(adsk.core.CommandEventHandler):
    """実際のコード実行を担当するイベントハンドラ"""

    def __init__(
        self,
        code_to_exec: str,
        namespace: dict[str, Any],
        result_container: CommandExecutionState,
    ) -> None:
        """CommandExecuteイベントハンドラ

        Args:
            code_to_exec (str): 実行するPythonコード
            namespace (dict[str, Any]): 実行時に使用する名前空間
            result_container (ExecutionContainer): コマンドの実行結果を保存するためのコンテナ

        """
        super().__init__()
        self.code_to_exec = code_to_exec
        self.namespace = namespace
        self.result_container = result_container

    def notify(self, args: adsk.core.CommandEventArgs) -> None:
        """コマンドが実行されたときに呼び出され、渡されたコードを実行する"""
        # 出力をキャプチャするためのバッファ
        capture_buffer = io.StringIO()

        try:

            def custom_print(*values: object) -> None:
                log_msg = " ".join(str(arg) for arg in values)
                futil.log(log_msg, force_console=True)

                print(*values, file=capture_buffer)

            local_namespace = self.namespace.copy()
            local_namespace["print"] = custom_print

            # exec関数で文字列として渡されたコードを実行
            exec(self.code_to_exec, local_namespace)  # noqa: S102

            # 実行結果をコンテナに保存
            self.result_container.code_result = capture_buffer.getvalue()

        except Exception:
            output = capture_buffer.getvalue()  # エラーが発生したときまでの標準出力
            error_traceback = traceback.format_exc()
            self.result_container.code_result = f"{output}\n--- TRACEBACK ---\n{error_traceback}"

        finally:
            capture_buffer.close()


class CommandDestroyHandler(adsk.core.CommandEventHandler):
    """コマンドが破棄されるときに、その定義を削除するハンドラ

    一時的に定義したコマンドを実行し終えたときに自動で定義を消去する
    """

    def __init__(self, result_container: CommandExecutionState) -> None:
        super().__init__()
        self.result_container = result_container

    def notify(self, args: adsk.core.CommandEventArgs) -> None:
        try:
            # イベントの引数からコマンド定義を取得して削除する
            # これで安全なタイミングでクリーンアップできる
            cmd_def = args.command.parentCommandDefinition
            if cmd_def:
                cmd_def.deleteMe()
        except Exception as e:
            futil.handle_error(f"Failed to delete command definition: {e!s}")
        finally:
            # コマンドの実行が終了したことをコンテナに記録
            self.result_container.is_finished = True


class CommandCreatedHandler(adsk.core.CommandCreatedEventHandler):
    def __init__(
        self,
        code_to_exec: str,
        namespace: dict,
        result_container: CommandExecutionState,
        handlers_list: list[adsk.core.CommandEventHandler],
    ) -> None:
        """CommandCreatedイベントハンドラ

        Args:
            code_to_exec (str): 実行するPythonコード
            namespace (dict): 実行時に使用する名前空間
            result_container (ExecutionResult): コマンドの実行結果を保存するためのコンテナ。
                このクラスの中でコンテナの属性が変更される。
            handlers_list (list[adsk.core.CommandEventHandler]):
                イベントハンドラのリスト

        """
        super().__init__()
        self.code_to_exec = code_to_exec
        self.namespace = namespace
        self.result_container = result_container
        self.handlers = handlers_list

    def notify(self, args: adsk.core.CommandEventArgs) -> None:
        try:
            cmd = adsk.core.Command.cast(args.command)

            # CommandExecuteイベントハンドラを接続
            on_execute = CommandExecuteHandler(
                self.code_to_exec,
                self.namespace,
                self.result_container,
            )
            self.handlers.append(on_execute)
            cmd.execute.add(on_execute)

            on_destroy = CommandDestroyHandler(self.result_container)
            self.handlers.append(on_destroy)
            cmd.destroy.add(on_destroy)

            # このコマンドはUIを持たず、即座に実行される
            cmd.isAutoExecute = True

        except Exception:
            self.result_container.fusion_error = FusionExecutionError(
                "Failed to set up the command execution environment.",
            )

            # エラー時に、強制的に終了状態にする
            self.result_container.is_finished = True


def execute_code_in_transaction(
    code: str,
    transaction_name: str = "Python Script Execution",
) -> str:
    """任意のPythonスクリプトを単一のトランザクションとして実行する

    Args:
        code (str): 実行するPythonコード
        transaction_name (str): アンドゥスタックに表示されるトランザクションの説明

    Returns:
        str: 実行結果の文字列（標準出力）

    """
    if not code:
        raise InvalidUserInputError("Parameter 'code' cannot be empty")

    app = adsk.core.Application.get()
    ui = app.userInterface
    cmd_def = None

    # イベントハンドラがGCされないように参照を保持するリスト
    handlers: list[adsk.core.EventHandler] = []

    # コマンドの実行結果を保存するためのコンテナ
    container = CommandExecutionState()

    try:
        # 他のコマンドと衝突しないように一意なIDを生成
        # 一時的なコマンドのIDなのでランダムでOK
        command_id = f"temp_transactional_executor_{uuid.uuid4()}"

        # スクリプト実行時に使用できる変数を用意
        design = adsk.fusion.Design.cast(app.activeProduct)
        namespace = {
            "adsk": adsk,
            "app": app,
            "ui": ui,
            "design": design,
            "root_comp": design.rootComponent if design else None,
            "traceback": traceback,
        }

        # 一時的なコマンドを作成
        # 1度実行すると自動でコマンド定義が削除される
        cmd_def = ui.commandDefinitions.addButtonDefinition(
            command_id,
            transaction_name,
            transaction_name,
        )

        on_created = CommandCreatedHandler(
            code,
            namespace,
            result_container=container,
            handlers_list=handlers,
        )
        handlers.append(on_created)
        cmd_def.commandCreated.add(on_created)

        cmd_def.execute()

        while not container.is_finished:
            # コマンドの実行が終了するまで待機
            # Fusionのコマンドは非同期で実行されるため、ここで待機する
            adsk.doEvents()

        if container.fusion_error:
            raise container.fusion_error

    except Exception as e:
        if isinstance(e, (FusionExecutionError, InvalidUserInputError)):
            raise
        futil.handle_error(
            f"An unexpected error occurred while executing code in transaction: {e!s}",
        )
        raise FusionExecutionError("An unexpected infrastructure error occurred.") from e

    return container.code_result or ""
