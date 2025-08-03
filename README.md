# Fusion MCP

Autodesk Fusionを操作するMCPサーバー

LLMとFusionを接続し、自然言語による対話でCADの操作を可能にします。

## 構成

- **MCPサーバー** (`mcp-server/`):
  LLMとFusionアドインを接続するMCP(Model Context Protocol)サーバー

- **Fusionアドイン** (`mcp-addin/`):
  MCPサーバーからリクエストを受けて、実際にFusionを操作するアドイン
  
## MCPツール

- `execute_code`: Pythonコードを実行する。Fusion APIを使用してFusionを操作できます
- `get_viewport_screenshot`: Fusionのアクティブなビューポートのスクリーンショットを取得する
- `list_user_parameters`: User Parametersの一覧を取得する
- `set_user_parameter`: User Parameterの式を設定する

## セットアップ

### 必要なもの
- Autodesk Fusion
- MCPクライアント (Claude Desktop, Cursorなど)
- Python
- uv

### 手順

1. **リポジトリをダウンロードします。**

2. **MCPクライアントにMCPサーバーを登録します。**
   
   Claude Desktopの場合：
   
   左上のメニュー > File > Settings > Developer > Edit Configから`claude_desktop.json`を開き、以下を追加します。
   
   ```json
   {
     "mcpServers": {
       "fusion": {
         "command": "uvx",
         "args": [
           "--from",
           "[リポジトリへの絶対パス]/fusion-mcp/mcp-server",
           "fusion-mcp-server"
         ]
       }
     }
   }
   ```

3. **Fusionにアドインを登録します。**
   
   1. FusionでUTILITIES > ADD-INS からScripts and Add-Insウィンドウを開きます。 
   2. 「+」ボタン > Script or add-in from device から、ダウンロードした `fusion-mcp/mcp-addin`フォルダを選択します。
   3. リストにmcp-addinが追加されるので、Runをクリックして起動します。\
      Run on Startupを有効にすると、Fusion起動時にアドインが自動で実行されます。
   
## ⚠️ 重要な注意点

このFusionアドインは、**LLMが生成した任意のPythonコードをFusion内で実行します。これにはセキュリティ上のリスクがあります。**
使用する前にFusionデータのバックアップを作成し、LLMが生成したコードを確認するようにしてください。

## 使用時のポイント

Fusion MCP単体では、LLMがFusionをうまく操作できない場合がほとんどです。
次のような指示を直接与えたり、ツール使用前にLLMに考えてもらうと効果的です。

- **具体的な数値を指定する**: 「10mm押し出す」など明確な値を与える
- **操作手順を明確にする**: 「まず部品を選択、次に押し出し」のように手順をわける
- **Fusion APIドキュメントを提供する**: APIのドキュメントやサンプルコードを渡す
  - [Fusion Help | Welcome to the Fusion API](https://help.autodesk.com/view/fusion360/ENU/?guid=GUID-A92A4B10-3781-4925-94C6-47DA85A4F65A)
  - [Fusion360DevTools](https://github.com/autodeskfusion360/fusion360devtools)

これらのMCPサーバーも組み合わせると便利です。

- **[Sequential Thinking MCP Server](https://github.com/modelcontextprotocol/servers/tree/main/src/sequentialthinking)**: LLMが設計を段階的に考えてくれるようになります
- **[Context7 MCP Server](https://github.com/upstash/context7)**: LLMがドキュメントを探して参照できるようになります
  
## クレジット

このプロジェクトは[ahujasid](https://github.com/ahujasid)さんによる
[blender-mcp](https://github.com/ahujasid/blender-mcp)
を参考に作成しました。

## ライセンス

MIT License
