"""unified.csv のカラム名をユニーク化し、ダミー値を投入する。

実行: python scripts/prepare_unified_csv.py
"""
from __future__ import annotations

import csv
import sys
from datetime import datetime
from pathlib import Path

ROOT = Path(__file__).resolve().parents[1]
CSV_PATH = ROOT / "data" / "master" / "unified.csv"
OUT_PATH = CSV_PATH  # 上書き


def rename_headers(headers: list[str]) -> list[str]:
    """重複する '含有量' を '成分1_含有量', '成分2_含有量', ... にリネームする。"""
    new_headers: list[str] = []
    for i, h in enumerate(headers):
        if h == "含有量":
            prev = headers[i - 1] if i > 0 else ""
            if prev.startswith("成分"):
                new_headers.append(f"{prev}_含有量")
            elif prev.startswith("材料"):
                new_headers.append(f"{prev}_含有量")
            else:
                new_headers.append(f"含有量_{i}")
        else:
            new_headers.append(h)
    return new_headers


# --- ダミー値マッピング ---

MARKET_PRICE_BASE: dict[str, float] = {
    "セルロースパルプ": 100.0,
    "ケイ酸塩鉱物": 28.0,
    "二酸化チタン": 450.0,
    "ポリエステル": 200.0,
    "レーヨン": 300.0,
    "ポリ塩化ビニル": 150.0,
    "PVC P800": 150.0,
    "酸化チタンR型": 450.0,
    "可塑剤DINP": 250.0,
    "カーボンブラック": 180.0,
    "炭酸カルシウム": 30.0,
    "黄色酸化鉄": 350.0,
    "安定剤Ca-Zn": 400.0,
    "シアニンググリーン": 800.0,
    "アルミナ硼珪酸ガラス": 120.0,
    "塩ビアクリル系樹脂": 160.0,
    "ポリスチレン": 180.0,
    "イソブタン": 90.0,
    "ジメチルエーテル": 100.0,
    "脂肪族炭化水素(C8-C16)": 110.0,
    "亜リン酸エステル": 500.0,
    "炭酸バリウム": 200.0,
    "バリウム化合物": 220.0,
    "ノニルフェノール": 300.0,
    "高沸点芳香族ナフサ": 150.0,
    "亜鉛化合物": 280.0,
    "鉱油": 80.0,
    "ニトリルゴム": 350.0,
    "塩化ビニル酢酸ビニル共重合樹脂": 200.0,
    "メチルエチルケトン": 120.0,
    "シクロヘキサン": 100.0,
    "アセトン": 90.0,
    "二酸化珪素": 60.0,
    "アクリル/塩ビ系樹脂": 180.0,
    "ポリアミド6（ナイロン6）": 350.0,
    "ポリ塩化ビニル樹脂": 150.0,
}

WK680_COMPOSITIONS: dict[str, str] = {
    "セルロースパルプ": "78%",
    "ケイ酸塩鉱物": "15%",
    "二酸化チタン": "10%",
}


def inflation_factor(date_str: str) -> float:
    if not date_str.strip():
        return 1.0
    try:
        year = int(date_str.split("/")[0])
    except (ValueError, IndexError):
        return 1.0
    factors = {
        2008: 0.75, 2009: 0.76, 2010: 0.78, 2011: 0.80,
        2012: 0.82, 2013: 0.84, 2014: 0.86, 2015: 0.88,
        2016: 0.90, 2017: 0.92, 2018: 0.95, 2019: 0.97,
        2020: 1.00, 2021: 1.05, 2022: 1.15, 2023: 1.20,
        2024: 1.25, 2025: 1.30, 2026: 1.35,
    }
    return factors.get(year, 1.0)


def get_market_price(component_name: str, date_str: str) -> str:
    base = MARKET_PRICE_BASE.get(component_name, 200.0)
    factor = inflation_factor(date_str)
    return f"{base * factor:.1f}"


def fill_dummy_values(row: list[str], headers: list[str]) -> list[str]:
    row = list(row)
    h_map = {name: idx for idx, name in enumerate(headers)}
    product_name = row[h_map["品名"]]
    date_str = row[h_map["改定時期"]]
    factor = inflation_factor(date_str)

    # WK-680RIP の含有量補完
    if "WK-680" in product_name:
        for comp_col in ["成分1", "成分2", "成分3"]:
            pct_col = f"{comp_col}_含有量"
            if comp_col in h_map and pct_col in h_map:
                comp_name = row[h_map[comp_col]]
                if comp_name in WK680_COMPOSITIONS and not row[h_map[pct_col]].strip():
                    row[h_map[pct_col]] = WK680_COMPOSITIONS[comp_name]

    # 市況単価ダミー値（成分1〜4）
    for i in range(1, 5):
        comp_col = f"成分{i}"
        price_col = f"［成分{i}］市況単価"
        if comp_col in h_map and price_col in h_map:
            comp_name = row[h_map[comp_col]].strip()
            if comp_name and not row[h_map[price_col]].strip():
                row[h_map[price_col]] = get_market_price(comp_name, date_str)

    # 燃動力ダミー値
    fuel_defaults = [
        ("燃動力1", "LNG", "［燃動力1］単価", 170.0),
        ("燃動力2", "電力", "［燃動力2］単価", 130.0),
    ]
    for name_col, default_name, price_col, base_price in fuel_defaults:
        if name_col in h_map and not row[h_map[name_col]].strip():
            row[h_map[name_col]] = default_name
        if price_col in h_map and not row[h_map[price_col]].strip():
            row[h_map[price_col]] = f"{base_price * factor:.1f}"

    # 労務費ダミー値
    labor_col = "労務費（時間当り）"
    if labor_col in h_map and not row[h_map[labor_col]].strip():
        row[h_map[labor_col]] = f"{900 * factor:.0f}"

    # 運賃ダミー値
    fare_col = "［運賃］円/m"
    if fare_col in h_map and not row[h_map[fare_col]].strip():
        row[h_map[fare_col]] = f"{48000 * factor / 128000:.4f}"

    return row


def main() -> None:
    with open(CSV_PATH, "r", encoding="utf-8") as f:
        reader = csv.reader(f)
        old_headers = next(reader)
        rows = list(reader)

    new_headers = rename_headers(old_headers)
    new_rows = [fill_dummy_values(row, new_headers) for row in rows]

    with open(OUT_PATH, "w", encoding="utf-8", newline="") as f:
        writer = csv.writer(f)
        writer.writerow(new_headers)
        writer.writerows(new_rows)

    print(f"完了: {len(new_rows)} 行を処理しました。")
    print(f"出力: {OUT_PATH}")


if __name__ == "__main__":
    main()
