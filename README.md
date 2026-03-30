# Fusion MCP

Autodesk Fusionを操作するためのMCP Server

## MCP Tools

- `execute_code`: PythonのコードをFusion内で実行する。Fusion APIを利用したモデリングが可能。
- `get_viewport_screenshot`: 現在のビューポートのスクリーンショットを取得する。
- `list_user_parameters`: User Parametersの一覧を取得する。
- `set_parameter`: User Parameterを更新する。

> [!DANGER]
> LLMが生成したPythonコードをFusion上で実行します。
> 重要なデータで扱う前にバックアップを取り、Toolの実行内容を確認するようにしてください。

## 仕組み

MCP ServerとFusion Add-inが連携して動作します。

- **MCP Server** (`mcp-server/`)：Toolの呼び出しを受けてFusion Add-inに処理を依頼する。
- **Fusion Add-in** (`mcp-addin/`)：Fusion上で動作し、Fusion APIを使って実際の処理を実行する。

## セットアップ

`uv`が必要です。

### 1. MCP ClientにMCP Serverを登録

各MCP Clientの設定方法に従ってください。

```json
{
  "mcpServers": {
    "fusion": {
      "command": "uvx",
      "args": [
        "--from",
        "<リポジトリへの絶対パス>/fusion-mcp/mcp-server",
        "fusion-mcp-server"
      ]
    }
  }
}
```

### 2. FusionにAdd-inを登録

1. Fusionで`UTILITIES > ADD-INS`を開く。
2. `+`ボタンから`Script or add-in from device`を選び、`fusion-mcp/mcp-addin`フォルダを選択する。
3. 追加された`mcp-addin`の`Run`トグルをONにする。

`Run on Startup`を有効にすると、Fusion起動時に自動でAdd-inが実行されます。

## 使い方のコツ

- エージェントのPlan Modeなどを利用する。
- Fusion APIのドキュメントやサンプルを参照させる。
    - [Fusion Help | Welcome to the Fusion API](https://help.autodesk.com/view/fusion360/ENU/?guid=GUID-A92A4B10-3781-4925-94C6-47DA85A4F65A)
    - [Fusion360DevTools](https://github.com/autodeskfusion360/fusion360devtools)

## クレジット

[ahujasid/blender-mcp](https://github.com/ahujasid/blender-mcp)を参考に作成しました。

## ライセンス

MIT License
