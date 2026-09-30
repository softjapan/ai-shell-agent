# AI Shell Command Agent

[![Python](https://img.shields.io/badge/Python-3.10%2B-blue.svg)](https://www.python.org/downloads/)
[![CI](https://github.com/softjapan/ai-shell-agent/actions/workflows/ci.yml/badge.svg)](https://github.com/softjapan/ai-shell-agent/actions/workflows/ci.yml)
[![License](https://img.shields.io/badge/License-MIT-green.svg)](LICENSE)

Google GeminiまたはOpenAIを使って自然言語からシェルコマンドを生成し、ローカルポリシーで検査してから、必要に応じて実行するCLIです。

> [!IMPORTANT]
> このツールの安全性検査は補助的なガードレールであり、OSサンドボックスではありません。表示されたコマンド、作業ディレクトリ、危険度を必ず確認してください。

## 特徴

- **プロバイダー選択**：Google GeminiとOpenAI APIをCLIオプションで切り替えられます。
- **実行が既定**：生成・検査の後、対話確認を経てコマンドを実行します。`--dry-run` で検査のみに切り替えられます。
- **シンプルな出力**：既定では生成コマンドと確認のみを表示します。詳細は `--verbose` で確認できます。
- **モデル非依存のローカル検査**：AI自身の安全性判断を信用せず、決定論的なルールで再検査します。
- **4段階の危険度**：`low`、`medium`、`high`、`blocked`。
- **高リスク時の警告**：`high` では実行前に警告と理由を表示します。`blocked` は実行できません。
- **実行制御**：シェルと作業ディレクトリを検証し、タイムアウトと終了コードを処理します。
- **構造化出力**：Pydanticモデルで成功・失敗、単一行、最大長などを検証します。
- **秘密情報を抑制**：APIエラー本文や作業ディレクトリのフルパスをAIへのプロンプトに含めません。

## 必要環境

- Python 3.10以上
- [uv](https://docs.astral.sh/uv/)（推奨）
- Google Gemini APIキーまたはOpenAI APIキー
- macOS/Linux上の `sh`、`bash`、`zsh`、`dash`、または`ksh`

## インストール

### uv（推奨）

```bash
git clone https://github.com/softjapan/ai-shell-agent.git
cd ai-shell-agent
uv sync --locked
```

### pip

```bash
python -m venv .venv
source .venv/bin/activate
python -m pip install -r requirements.txt
python -m pip install . --no-deps
```

利用するプロバイダーのAPIキーを設定します。両方を同時に設定する必要はありません。

```bash
# Google（既定プロバイダー）
export GEMINI_API_KEY="your-gemini-api-key"

# OpenAI
export OPENAI_API_KEY="your-openai-api-key"
```

Geminiキーは[Google AI Studio](https://aistudio.google.com/app/apikey)、OpenAIキーは[OpenAI Platform](https://platform.openai.com/api-keys)から取得できます。

APIキーは環境変数が最優先です。任意で `.env` を使う場合は、環境変数に未設定のキーだけが補完されます（環境変数を上書きしません）。`.env.example` をコピーして使ってください。`.env` はGit管理から除外されます。

```bash
cp .env.example .env
# .env を編集して、使うプロバイダーのキーを設定
```

`.env` の場所は `--env-file PATH` で変更でき、`--env-file /dev/null` で読み込みを無効化できます。

## 使用方法

### Google Gemini（既定）

```bash
uv run ai-shell-agent "現在のディレクトリにあるPythonファイルを表示"
```

明示的にも指定できます。

```bash
uv run ai-shell-agent --provider google "現在のディレクトリを表示"
```

### OpenAI

```bash
uv run ai-shell-agent --provider openai "現在のディレクトリを表示"
```

既定プロバイダーを恒久的にOpenAIへ変更するには、環境変数（または`.env`）を設定します。`--provider` を付ければ常に上書きできます。

```bash
export AI_SHELL_AGENT_PROVIDER="openai"
uv run ai-shell-agent "現在のディレクトリを表示"          # OpenAIを使用
uv run ai-shell-agent --provider google "現在のディレクトリを表示"  # 明示指定が優先
```

既定モデルはGoogleが `gemini-2.5-flash`、OpenAIが `gpt-4o-mini` です。任意の利用可能なモデルを指定できます。

```bash
uv run ai-shell-agent --provider openai --model gpt-4o "Gitの変更内容を表示"
```

### 検査のみ（--dry-run）

`--dry-run` を付けると、生成と危険度判定だけを行い実行しません。

```bash
uv run ai-shell-agent --dry-run "現在のディレクトリにあるPythonファイルを表示"
```

既定はシンプルな出力です。

```text
[AI Answer]: find . -maxdepth 1 -name '*.py' -print
Dry run only. Re-run without --dry-run to allow confirmation and execution.
```

`--verbose` を付けると、プロバイダー、モデル、危険度、作業ディレクトリ、シェルなどの詳細も表示されます。

```text
Command   find . -maxdepth 1 -name '*.py' -print
Details   現在のディレクトリ直下にあるPythonファイルを表示します。
Provider  openai  (gpt-4o-mini)
Risk      low
          ↳ matches a recognized read-only command
Workdir   /path/to/project
Shell     /bin/zsh
Dry run only. Re-run without --dry-run to allow confirmation and execution.
```

### 実行（既定）

```bash
uv run ai-shell-agent "現在のディレクトリを表示"
uv run ai-shell-agent --provider openai "現在のディレクトリを表示"
```

既定では生成・検査の後に対話確認へ進みます。すべての危険度で `Execute? Y/N:` に同意すると実行します。`high` では実行前に警告と理由を表示します。`blocked` は実行できません。区切り線や `✓ / ✗ exit N` などの詳細は `--verbose` で表示されます。

色出力はTTYのときだけ有効で、`--no-color` または環境変数 `NO_COLOR` で無効化できます。

### オプション

```text
--provider {google,openai}  AIプロバイダー（既定: google、AI_SHELL_AGENT_PROVIDERで変更可）
--dry-run                   検査のみ（生成と危険度判定を行い実行しない）
--verbose                   詳細表示（プロバイダー、モデル、危険度、区切り、終了ステータス）
--timeout SECONDS           コマンド実行の制限時間（既定: 30秒）
--api-timeout SEC           AI APIの制限時間（既定: 30秒）
--cwd PATH                  コマンドの作業ディレクトリ
--env-file PATH             環境変数に無いキーのみ補完する.env（既定: .env）
--model NAME                モデル名（既定: プロバイダー別）
--no-color                  ANSI色出力を無効化（NO_COLORでも無効化可）
--version                   バージョンを表示
```

旧来の呼び出し方も互換ラッパーとして利用できます。

```bash
uv run python as.py "ファイル一覧を表示"
uv run python as.py --provider openai "ファイル一覧を表示"
```

## 安全ポリシー

代表的な分類例です。ルールは `ai_shell_agent/policy.py` にあります。

| 危険度 | 例 | 動作 |
|---|---|---|
| low | `pwd`, `ls`, `git status` | Y/N確認後に実行可能 |
| medium | ファイル作成、ネットワーク、未知のコマンド | Y/N確認後に実行可能 |
| high | ファイル削除、権限変更、プロセス終了 | 警告と理由を表示し、Y/N確認後に実行可能 |
| blocked | `sudo`、リモートスクリプト実行、ディスク消去、ルート削除 | 実行不可 |

ポリシーは文字列解析に基づくため、誤検出や見逃しの可能性があります。機密環境では、コンテナ、専用ユーザー、OSサンドボックスなど追加の隔離を使用してください。

## 終了コード

| コード | 意味 |
|---:|---|
| 0 | dry-run完了、キャンセル、またはコマンド成功 |
| 2 | 引数、APIキー、生成処理のエラー |
| 3 | ローカル安全ポリシーによるブロック |
| 4 | コマンド開始前の実行エラー |
| 124 | コマンドタイムアウト |
| 130 | Ctrl+Cによる中断 |
| その他 | 実行したコマンドの終了コード |

## アーキテクチャ

```text
ユーザー入力 + provider
    ↓
ai_shell_agent.generator   Google/OpenAIによるCommandPlan生成
    ↓
ai_shell_agent.models      Pydanticによる構造検証
    ↓
ai_shell_agent.policy      プロバイダー非依存のローカル危険度判定
    ↓
ai_shell_agent.cli         dry-run・危険度別の対話確認
    ↓
ai_shell_agent.executor    subprocess・timeout・終了コード
```

AI生成とプロセス実行を分離しているため、テストでは両境界をモックし、外部APIや実コマンドを呼びません。

## 開発

```bash
uv sync --locked --group dev
uv run black --check .
uv run ruff check .
uv run pyright
uv run pytest
uv build
```

自動修正する場合：

```bash
uv run black .
uv run ruff check --fix .
```

## プロジェクト構造

```text
ai-shell-agent/
├── ai_shell_agent/
│   ├── cli.py          # provider選択、dry-run、確認、終了コード
│   ├── config.py       # 環境変数優先の任意.env補完
│   ├── executor.py     # 制御されたサブプロセス実行
│   ├── formatting.py   # 依存なしのANSIカラー補助
│   ├── generator.py    # Google/OpenAI連携とAPIエラー処理
│   ├── models.py       # 構造化出力とドメイン型
│   └── policy.py       # ローカル安全ポリシー
├── tests/              # API・プロセスをモックした単体テスト
├── .github/workflows/  # CI
├── .env.example        # キー名のみのテンプレート
├── as.py               # 後方互換ラッパー
├── pyproject.toml
├── requirements.txt
├── uv.lock
└── LICENSE
```

## ライセンス

[MIT License](LICENSE)

## 免責事項

このツールは生成されたコマンドの完全な安全性や正確性を保証しません。実行結果は利用者の責任で確認してください。
