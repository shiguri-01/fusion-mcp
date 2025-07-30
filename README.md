# Fusion MCP

Autodesk Fusionを操作するためのMCPサーバー

LLMとFusionを接続し、自然言語による対話でCAD操作を可能にします。

## 構成

- **MCP Server** (`mcp-server/`):
  LLMとFusion Addinを接続するMCP(Model Context Protocol)サーバー

- **Fusion Add-in** (`mcp-addin/`):
  MCP Serverからのリクエストを受け取り、FusionでCAD操作を実行するアドイン


## セットアップ

### 必要なもの
- Autodesk Fusion
- MCP Client (Claude Desktop, Cursorなど)
- Python
- uv

### 手順

1. **リポジトリをダウンロード**

2. **MCP ClientにServerを登録**
   
   Claude Desktopの場合：
   
   Fiile > Settings > Developer > Edit Configをクリックします。
   エクスプローラーが開くので`claude_desktop.json`を開き、以下の内容を追加します。
   
   ```json
   {
     "mcpServers": {
       "fusion": {
         "command": "uvx",
         "args": [
           "--from",
           "path_to_downloaded/fusion-mcp/mcp-server",
           "fusion-mcp-server"
         ]
       }
     }
   }
   ```

3. **Fusionにアドインを登録**
   
   UTILITIES > ADD-INS > 「+」ボタン > Script or add-in from device > `fusion-mcp/mcp-addin` フォルダを選択します。
   mcp-addinが追加されるので、Runをオンにします。
   
   Run on Startupを有効にすると、Fusion起動時に自動でアドインが読み込まれます。
   
## ⚠️ 重要な注意点

**LLMが生成したPythonコードをFusion内で実行する仕組みのため、セキュリティリスクがあります。**
使用する前にFusionデータのバックアップを作成し、LLMが生成したコードを確認するようにしてください。

## 使用時のポイント

Fusion MCPだけでは、LLMがCADをうまく扱えない場合がほとんどです。
次のことを試してみてください。

- **具体的な数値を指定** - 「10mm伸ばして」など明確な値を含める
- **事前に設計を考えさせる** - CAD操作前に数値を含めた設計プランを作成・検証してもらう
- **操作手順を明確化** - 「まず部品を選択、次に押し出し」など段階的な指示
- **Fusion APIドキュメントを提供** - 複雑な操作時は関連APIの情報を渡す
- **スクリーンショットを活用** - 現在の状態を画像で共有

これらのMCPサーバーも組み合わせると便利です。

- **[Sequential Thinking MCP Server](https://github.com/modelcontextprotocol/servers/tree/main/src/sequentialthinking)** - LLMが設計を段階的に考えてくれるようになります
- **[Context7 MCP Server](https://github.com/upstash/context7)** - LLMがドキュメントを探して参照できるようになります
  
## Credit

このプロジェクトは[ahujasid](https://github.com/ahujasid)さんによる
[blender-mcp](https://github.com/ahujasid/blender-mcp)
を参考に作成しました。
