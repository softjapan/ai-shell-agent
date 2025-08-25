# AI Shell Command Agent

[![Python](https://img.shields.io/badge/Python-3.10+-blue.svg)](https://www.python.org/downloads/)
[![License](https://img.shields.io/badge/License-MIT-green.svg)](LICENSE)
[![Code Style](https://img.shields.io/badge/code%20style-black-000000.svg)](https://github.com/psf/black)

AIを使用して自然言語からシェルコマンドを自動生成し、安全に実行するためのエージェントツール

## 🎥 デモ

https://github.com/user-attachments/assets/21d4e708-f436-4887-9c21-ed1e0e4f2a32

## ✨ 特徴

- 🤖 **AI駆動**: Google Gemini AIを使用してインテリジェントなコマンド生成
- 🛡️ **安全性重視**: 実行前に必ず確認を求める
- 🌍 **多言語対応**: ユーザーの入力言語に合わせて応答
- 🚀 **効率的**: 最適なシェルコマンドを自動選択
- 📚 **学習可能**: AIが思考プロセスを説明

## 🚀 インストール

### 前提条件

- Python 3.10以上
- Google Gemini API キー

### 1. リポジトリのクローン

```bash
git clone https://github.com/softjapan/ai-shell-agent.git
cd ai-shell-agent
```

### 2. 依存関係のインストール

```bash
# uvを使用（推奨）
uv sync

# または pip を使用
pip install -r requirements.txt
```

### 3. 環境変数の設定

```bash
export GEMINI_API_KEY="your-api-key-here"
```

## 📖 使用方法

### 基本的な使用方法

```bash
python as.py "ファイル一覧を表示"
```

### 使用例

```bash
# ファイル一覧を表示
python as.py "ファイル一覧を表示"

# ディレクトリを作成
python as.py "新しいフォルダを作成"

# ファイルを検索
python as.py "特定のファイルを検索"

# システム情報を表示
python as.py "システムの詳細情報を表示"
```

## 🔧 設定

### 環境変数

| 変数名 | 説明 | 必須 |
|--------|------|------|
| `GEMINI_API_KEY` | Google Gemini API キー | ✅ |

### API キーの取得方法

1. [Google AI Studio](https://makersuite.google.com/app/apikey) にアクセス
2. Google アカウントでログイン
3. "Create API Key" をクリック
4. 生成されたキーをコピーして環境変数に設定

## 🏗️ アーキテクチャ

```
┌─────────────────┐    ┌─────────────────┐    ┌─────────────────┐
│   ユーザー入力   │───▶│   AI エージェント  │───▶│   シェルコマンド   │
└─────────────────┘    └─────────────────┘    └─────────────────┘
                              │
                              ▼
                       ┌─────────────────┐
                       │   実行確認      │
                       └─────────────────┘
                              │
                              ▼
                       ┌─────────────────┐
                       │   コマンド実行   │
                       └─────────────────┘
```

## 🛠️ 開発

### 開発環境のセットアップ

```bash
# 開発用依存関係のインストール
uv sync --group dev

# コードフォーマット
uv run black .

# リンター
uv run ruff check .

# テスト実行
uv run pytest
```

### プロジェクト構造

```
ai-shell-agent/
├── as.py                 # メインスクリプト
├── pyproject.toml        # プロジェクト設定
├── requirements.txt      # 依存関係
├── README.md            # このファイル
├── LICENSE              # ライセンス
└── .github/             # GitHub設定
    └── workflows/       # CI/CD設定
```

## 🤝 コントリビューション

プロジェクトへの貢献を歓迎します！

### コントリビューションの手順

1. このリポジトリをフォーク
2. 新しいブランチを作成 (`git checkout -b feature/amazing-feature`)
3. 変更をコミット (`git commit -m 'Add some amazing feature'`)
4. ブランチにプッシュ (`git push origin feature/amazing-feature`)
5. プルリクエストを作成

### 開発ガイドライン

- コードは [Black](https://github.com/psf/black) でフォーマット
- 型ヒントを使用
- ドキュメント文字列を追加
- テストを書く

## 📝 ライセンス

このプロジェクトは [MIT License](LICENSE) の下で公開されています。

## ⚠️ 免責事項

- このツールは教育・開発目的で提供されています
- 生成されたコマンドの実行は自己責任で行ってください
- システムに影響を与える可能性のあるコマンドには注意してください

## 🙏 謝辞

- [Google Gemini AI](https://ai.google.dev/) - AIモデルの提供
- [Pydantic AI](https://ai.pydantic.dev/) - AIエージェントフレームワーク
- このプロジェクトに貢献してくださったすべての方々

## 📞 サポート

問題や質問がある場合は、[Issues](https://github.com/softjapan/ai-shell-agent/issues) を作成してください。

## 🔗 関連リンク

- [Google AI Studio](https://makersuite.google.com/app/apikey)
- [Pydantic AI Documentation](https://ai.pydantic.dev/)
- [Python Documentation](https://docs.python.org/)

---

⭐ このプロジェクトが役に立ったら、スターを付けてください！
