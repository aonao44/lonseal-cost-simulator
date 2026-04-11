# CLAUDE.md

思考は英語で行い、最終的な出力は必ず日本語で提供すること。

## プロジェクト概要

原材料価格交渉シミュレーターの PoC。ロンシール工業の購買部門が仕入先からの値上げ要請の妥当性をデータに基づいて判断するためのツール。**PoC フェーズ**であり、本番品質・本番インフラの提案は不要。

## コマンド

```bash
# 環境構築
python3 -m venv .venv
source .venv/bin/activate
pip install -e .[dev]

# 起動
streamlit run app.py

# テスト
pytest

# ベクトルDB初期投入
python scripts/seed_vectordb.py

# 統合CSV生成
python scripts/generate_unified_csv.py
```

## 技術スタック

- Python 3.11 / Streamlit
- Gemini 2.5 Pro（PDF からの構造化データ抽出）
- Gemini Embedding 2（`gemini-embedding-2-preview`、ドキュメントのベクトル化）
- ChromaDB（ベクトルDB、ローカル永続化）
- API キーは `.env` に `GEMINI_API_KEY` として設定

## ディレクトリ構成の意図

```
src/drawing_poc/       # アプリケーション本体（旧PoC名が残っているがリネーム予定）
  config.py            # 設定・パス解決。環境変数はここで一元管理
  embedding.py         # Gemini Embedding API 呼び出し
  vector_store.py      # ChromaDB 操作（upsert/query/reset）
  service.py           # ユースケース層（登録・検索）
  ui.py                # Streamlit UI
scripts/               # 一括処理スクリプト（DB投入、CSV生成）
data/master/           # 構造化済みマスタデータ（CSV）
data/chroma/           # ChromaDB 永続化先
data/uploads/          # アップロードファイル保存先
サンプルデータ/          # 先方提供の原本ドキュメント（編集禁止）
Pocのゴール/            # ゴールイメージ（シミュレーター画面・データスキーマ）
docs/                  # 要件定義書・タスク一覧
```

## データ構造

- **統合CSV**（`data/master/unified.csv`）: ゴールCSV（`Pocのゴール/P.04データイメージ.csv`）と同じ77カラムのフラット形式。1行 = 1品目の1回の価格改定
- **個別CSV**（`data/master/products.csv` 等）: 正規化された参照用データ。unified.csv の元データ
- **ベクトルDB**（ChromaDB コレクション `raw_materials`）: 仕様書PDF・交渉資料PDF・改訂履歴XLS・マスタCSV 計52件を格納済み
- データの充足状況は `data/master/README.md` に記載。市況単価・燃動力費・労務費・運賃は外部データのため空欄

## 開発フロー

- 開発開始前に `docs/requirements.md` を読み、要件・スコープを把握すること
- タスク一覧は `docs/tasks.md`
- シミュレーター画面の参照UIは `Pocのゴール/P.05シミュレーター.pdf`

## コーディング規約

- PEP 8 準拠
- 型ヒント必須（`from __future__ import annotations` を先頭に）
- `@ts-ignore` 禁止、型エラーは根本から修正
- try-catch でエラーを握りつぶさない
- 機能追加時はテストも追加。既存テストの削除・スキップ禁止

## 禁止事項

- `.env` ファイルの変更禁止
- API キーや認証情報のハードコード禁止
- `main` ブランチへの直接コミット禁止
- `サンプルデータ/` 配下のファイルの編集・削除禁止（先方提供の原本）
- PoC スコープ外の提案禁止（本番デプロイ、認証基盤、CI/CD パイプライン等）
- ライブラリの追加・変更は事前に確認を取ること
