"""unified.csv の読込・パース。"""
from __future__ import annotations

import pandas as pd

from simulator.config import UNIFIED_CSV_PATH


def load_unified_data() -> pd.DataFrame:
    """unified.csv を読み込んで DataFrame を返す。"""
    return pd.read_csv(UNIFIED_CSV_PATH, dtype=str).fillna("")


def get_product_names() -> list[str]:
    """品目名の一覧をソート済みで返す。"""
    df = load_unified_data()
    return sorted(df["品名"].unique().tolist())


def get_product_data(product_name: str) -> pd.DataFrame:
    """指定品目のデータを改定時期の昇順で返す。"""
    df = load_unified_data()
    product_df = df[df["品名"] == product_name].copy()
    if product_df.empty:
        return product_df
    product_df["改定時期_sort"] = pd.to_datetime(
        product_df["改定時期"], format="%Y/%m/%d", errors="coerce"
    )
    return product_df.sort_values("改定時期_sort", na_position="last").drop(columns=["改定時期_sort"])
