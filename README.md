# ai-proofreader

> 出版物PDFを AWS Bedrock 上の Claude に直接読ませて校正するプロトタイプ

日本語の書籍原稿（縦書き・横書き問わず）を PDF のままアップロードすると、誤字脱字・表記ゆれ・文法エラーをカード形式で一覧表示する Web アプリケーションです。

## なぜ作っているか

ある出版社の校正支援ツールを利用する中で、以下の課題を感じていました：

- **見落としが多い** — 明らかな誤字を拾えない
- **ノイズが多い** — 好みの範囲の指摘が大量に出る
- **誤認識が多い** — 正しい文字列を誤りと判定する

これらの根本原因は、**PDF からテキストを抽出してから AI に渡す**設計にあると考えました。このアプローチだと、ノンブル（ページ番号）・柱（章タイトル）が本文に混入し、縦書きの読み順が崩れ、ルビが本文に紛れ込みます。

本プロジェクトでは **PDF をそのまま Claude に渡し、レイアウト情報を含めて処理する**設計を採用し、実用レベルの校正精度を目指しています。

## 技術スタック

### バックエンド
- Python 3.12 / FastAPI
- AWS Bedrock (`jp.anthropic.claude-sonnet-4-6`)
- boto3 / pypdf

### フロントエンド
- React 18 / Vite 5

### AI
- AWS Bedrock 経由で Claude Sonnet 4.6 を利用
- PDF ネイティブ入力（Anthropic API の `document` 型）
- `temperature=0.0` で出力を安定化

## アーキテクチャの特徴

### 1. PDF を直接 Claude に渡す
一般的な AI 校正アプリは PDF からテキスト抽出して AI に渡しますが、本アプリは PDF を base64 エンコードしてそのまま送信しています。Claude がレイアウトを理解した上で、本文のみを校正対象として判断します。

**メリット:**
- ノンブル・柱・ヘッダーを自動除外
- 縦書き・ルビ・傍点に対応
- スキャン画像 PDF でも OCR 相当の処理が可能

### 2. 100 ページ制限への対応
Bedrock Claude API の仕様により 1 リクエスト最大 100 ページ。大きな書籍原稿に対応するため、`pypdf` で 50 ページずつに分割し、各チャンクの結果を集約しています。元 PDF の通しページ番号をチャンクを跨いで正しく管理します。

### 3. プロンプトエンジニアリング
プロンプト改善だけで校正精度は大きく変わります。本プロジェクトでは以下を徹底しています：

- **System プロンプト**で「ベテラン校正者」の役割を設定
- **Few-shot 例**で誤字脱字・表記ゆれの判断基準を具体化
- **「絶対に指摘しないこと」リスト**で誤検知を抑制（文体の好み、ファクト、意図的な表記等）
- **Severity 基準の明文化**（high / medium / low の定義）
- **引用の厳密化**でハルシネーションを防止（原文からの逐語引用を強制）
- **構造化 JSON 出力**で後続処理を容易に

詳しくは [`prompt.py`](./prompt.py) を参照。

### 4. 長時間処理への対応
大きな PDF では Bedrock の呼び出しに数分かかることがあるため：
- `boto3` の `read_timeout` を 600 秒に拡張
- 処理進捗をサーバーログに逐次出力

## セットアップ

### 事前準備
- Python 3.12+
- Node.js 20.16+
- AWS アカウント（Bedrock で `jp.anthropic.claude-sonnet-4-6` モデルへのアクセス許可が必要）

### バックエンド

```bash
python -m venv venv
source venv/bin/activate
pip install -r requirements.txt

cp .env.example .env  # .env を編集し、AWS 認証情報を設定

uvicorn main:app --reload --port 8000
```

### フロントエンド

```bash
cd frontend
npm install
npm run dev
```

ブラウザで http://localhost:5173 を開き、PDF をアップロードします。

## 開発ロードマップ

現在 **Phase 1（プロンプト改善）まで完了**。

- [x] **Phase 1**: プロンプト改善と構造化出力
  - System プロンプト導入
  - Few-shot 例によるルール明文化
  - Severity 基準の明確化
  - JSON 出力化
- [ ] **Phase 2**: PDF ビューアと左右分割 UI
  - `react-pdf` を組み込み
  - カードクリックで該当ページにジャンプ
- [ ] **Phase 3**: 精度ブースト機構
  - Extended Thinking の活用
  - 2 パス検証（広く拾う → 精査）
  - カスタム用語辞書
- [ ] **Phase 4**: 実運用機能
  - 承認/却下ワークフロー
  - CSV / PDF エクスポート
  - 処理履歴保存

## プロジェクト構成

```
ai-proofreader/
├── main.py                # FastAPI エンドポイント
├── prompt.py              # AI プロンプト定義
├── .env                   # AWS 認証情報（git 管理外）
├── .gitignore
└── frontend/
    ├── package.json
    ├── src/
    │   ├── App.jsx        # メイン UI
    │   ├── App.css
    │   └── main.jsx
    └── vite.config.js
```

## ライセンス

プロトタイプ段階のため、現状ライセンス未定。業務利用や転用を検討される場合はお問い合わせください。
