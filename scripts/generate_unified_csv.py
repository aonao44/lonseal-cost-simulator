"""マスタCSV群をゴールCSVのフラット形式に統合するスクリプト.

products.csv + price_history.csv + negotiations.csv を結合し、
ゴールCSV（P.04データイメージ）と同じカラム構造で出力する。

Usage:
    python scripts/generate_unified_csv.py
"""

from __future__ import annotations

import csv
from pathlib import Path

ROOT_DIR = Path(__file__).resolve().parents[1]
MASTER_DIR = ROOT_DIR / "data" / "master"
OUTPUT_PATH = MASTER_DIR / "unified.csv"

# ゴールCSVのヘッダ（P.04データイメージに準拠）
HEADERS = [
    "文書番号",
    "品名",
    "分類番号（大分類）",
    "分類番号（中分類）",
    "分類番号（小分類）",
    "分類番号（商標）",
    "運送経路",
    "所要時間",
    "運送会社",
    "輸送距離",
    "成分1", "含有量",
    "成分2", "含有量",
    "成分3", "含有量",
    "成分4", "含有量",
    "成分5", "含有量",
    "成分6", "含有量",
    "成分7", "含有量",
    "成分8", "含有量",
    "成分9", "含有量",
    "成分10", "含有量",
    "材料1", "含有量",
    "材料2", "含有量",
    "材料3", "含有量",
    "材料4", "含有量",
    "材料5", "含有量",
    "材料6", "含有量",
    "材料7", "含有量",
    "材料8", "含有量",
    "材料9", "含有量",
    "材料10", "含有量",
    "元価格",
    "改定後の価格",
    "改定時期",
    "改定理由",
    "［成分1］市況単価",
    "［成分2］市況単価",
    "［成分3］市況単価",
    "［成分4］市況単価",
    "［成分1］市況情報",
    "［成分2］市況情報",
    "［成分3］市況情報",
    "［成分4］市況情報",
    "燃動力1",
    "［燃動力1］市況情報",
    "［燃動力1］単価",
    "燃動力2",
    "［燃動力2］市況情報",
    "［燃動力2］単価",
    "燃動力3",
    "［燃動力3］市況情報",
    "［燃動力3］単価",
    "燃動力4",
    "［燃動力4］市況情報",
    "［燃動力4］単価",
    "労務費（時間当り）",
    "［労務費］市況情報",
    "［運賃］円/m",
]


def load_products() -> dict[str, dict]:
    """products.csv を品目コード（システム）をキーとして読み込む."""
    products = {}
    with open(MASTER_DIR / "products.csv", encoding="utf-8") as f:
        reader = csv.DictReader(f)
        for row in reader:
            sys_code = row.get("品目コード（システム）", "").strip()
            doc_code = row.get("文書番号", "").strip()
            key = sys_code or doc_code
            if key:
                products[key] = row
    return products


def load_price_history() -> list[dict]:
    """price_history.csv を全件読み込む."""
    rows = []
    with open(MASTER_DIR / "price_history.csv", encoding="utf-8") as f:
        reader = csv.DictReader(f)
        for row in reader:
            rows.append(row)
    return rows


def load_negotiations() -> dict[str, list[dict]]:
    """negotiations.csv を品目コードをキーとして読み込む."""
    nego_map: dict[str, list[dict]] = {}
    with open(MASTER_DIR / "negotiations.csv", encoding="utf-8") as f:
        reader = csv.DictReader(f)
        for row in reader:
            code = row.get("品目コード", "").strip()
            if code:
                nego_map.setdefault(code, []).append(row)
    return nego_map


def find_negotiation_reason(
    negotiations: dict[str, list[dict]],
    product_code: str,
    revision_date: str,
) -> str:
    """交渉記録から改定理由を検索する."""
    entries = negotiations.get(product_code, [])
    for entry in entries:
        if entry.get("改定時期", "") == revision_date:
            return entry.get("値上げ理由", "")
    # 日付が完全一致しない場合は最も近いものを返す
    for entry in entries:
        nego_date = entry.get("改定時期", "")
        if nego_date and revision_date and nego_date[:7] == revision_date[:7]:
            return entry.get("値上げ理由", "")
    return ""


def build_row(product: dict, price_row: dict | None, reason: str) -> list[str]:
    """1行分のデータを構築する."""
    row = [""] * len(HEADERS)

    # 品目基本情報
    row[0] = product.get("文書番号", "")
    row[1] = product.get("品名", "")
    row[2] = product.get("大分類", "")
    row[3] = product.get("中分類", "")
    row[4] = product.get("小分類", "")
    row[5] = product.get("商標", "")

    # 物流情報
    row[6] = product.get("運送経路", "")
    row[7] = product.get("所要時間", "")
    row[8] = product.get("運送会社", "")
    row[9] = product.get("輸送距離", "")

    # 成分1〜8（products.csvに8成分まであるので展開）
    for i in range(1, 9):
        comp = product.get(f"成分{i}", "")
        amount = product.get(f"含有量{i}", "")
        idx = 10 + (i - 1) * 2  # 成分1は index 10, 含有量1は 11
        row[idx] = comp
        row[idx + 1] = amount

    # 成分9, 10 と材料1〜10 は空（サンプルデータにないため）

    # 価格改定情報
    if price_row:
        # 元価格を計算（前の行から取得するのは複雑なので、price_historyの順序から推定）
        row[50] = ""  # 元価格は後で埋める
        row[51] = price_row.get("単価", "")
        row[52] = price_row.get("発効日", "")

    # 改定理由
    row[53] = reason

    return row


def compute_previous_prices(
    history_rows: list[dict],
) -> dict[tuple[str, str], str]:
    """品目コード+発効日 → 元価格のマッピングを作る."""
    # 品目コード+荷姿ごとにグループ化し、発効日で降順ソート
    groups: dict[tuple[str, str], list[dict]] = {}
    for row in history_rows:
        key = (row["品目コード"], row.get("荷姿名", ""))
        groups.setdefault(key, []).append(row)

    prev_map: dict[tuple[str, str], str] = {}
    for key, rows in groups.items():
        sorted_rows = sorted(rows, key=lambda r: r["発効日"])
        for i, row in enumerate(sorted_rows):
            if i > 0:
                prev_map[(row["品目コード"], row["発効日"])] = sorted_rows[i - 1]["単価"]
            else:
                prev_map[(row["品目コード"], row["発効日"])] = ""

    return prev_map


def main() -> None:
    products = load_products()
    history = load_price_history()
    negotiations = load_negotiations()
    prev_prices = compute_previous_prices(history)

    rows_out: list[list[str]] = []

    # 価格改定履歴がある品目: 改定ごとに1行
    processed_codes = set()
    for h_row in history:
        code = h_row["品目コード"]
        processed_codes.add(code)

        product = products.get(code, {})
        if not product:
            # 品目マスタにない場合はスキップ（コード不一致がないはず）
            print(f"  WARN: 品目コード {code} ({h_row['品目名']}) が products.csv にありません")
            continue

        reason = find_negotiation_reason(negotiations, code, h_row["発効日"])
        row = build_row(product, h_row, reason)

        # 元価格を埋める
        prev = prev_prices.get((code, h_row["発効日"]), "")
        row[50] = prev

        rows_out.append(row)

    # 価格改定履歴がない品目（K-75Z, ZEST PQ140）: 品目情報のみ1行
    for code, product in products.items():
        if code not in processed_codes:
            row = build_row(product, None, "")
            rows_out.append(row)

    # 出力
    with open(OUTPUT_PATH, "w", encoding="utf-8", newline="") as f:
        writer = csv.writer(f)
        writer.writerow(HEADERS)
        writer.writerows(rows_out)

    print(f"統合CSV出力完了: {OUTPUT_PATH}")
    print(f"  ヘッダ列数: {len(HEADERS)}")
    print(f"  データ行数: {len(rows_out)}")


if __name__ == "__main__":
    main()
