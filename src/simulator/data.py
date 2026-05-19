"""unified.csv / item_overrides.csv / market_prices.csv の読込・パース。"""
from __future__ import annotations

import pandas as pd

from simulator.calc import ItemCoeffs
from simulator.config import (
    ITEM_OVERRIDES_CSV_PATH,
    MARKET_PRICES_CSV_PATH,
    UNIFIED_CSV_PATH,
)


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


def load_item_overrides() -> pd.DataFrame:
    """item_overrides.csv を読み込み。存在しなければ空 DataFrame を返す。"""
    if not ITEM_OVERRIDES_CSV_PATH.exists():
        return pd.DataFrame()
    return pd.read_csv(ITEM_OVERRIDES_CSV_PATH, dtype=str).fillna("")


def _to_float(v: str, default: float) -> float:
    try:
        return float(str(v).strip())
    except (ValueError, TypeError):
        return default


def _to_float_or_none(v: str) -> float | None:
    if v is None:
        return None
    s = str(v).strip()
    if not s:
        return None
    try:
        return float(s)
    except ValueError:
        return None


def load_item_coeffs(doc_no: str) -> ItemCoeffs:
    """文書番号に対応する ItemCoeffs を返す。

    item_overrides.csv に該当行があれば各値で上書き、無ければデフォルト ItemCoeffs。
    """
    base = ItemCoeffs()
    df = load_item_overrides()
    if df.empty or "文書番号" not in df.columns:
        return base
    row_df = df[df["文書番号"].astype(str) == str(doc_no)]
    if row_df.empty:
        return base
    row = row_df.iloc[0]
    base.unit = str(row.get("unit", "")).strip() or base.unit
    base.product_weight_per_unit = _to_float(
        row.get("product_weight_kg_per_unit", ""), base.product_weight_per_unit
    )
    base.production_time_h_per_unit = _to_float(
        row.get("production_time_h_per_unit", ""), base.production_time_h_per_unit
    )
    base.labor_coeff = _to_float(row.get("labor_coeff", ""), base.labor_coeff)
    base.lng_usage = _to_float(row.get("lng_usage", ""), base.lng_usage)
    base.lng_coeff = _to_float(row.get("lng_coeff", ""), base.lng_coeff)
    base.elec_usage = _to_float(row.get("elec_usage", ""), base.elec_usage)
    base.elec_coeff = _to_float(row.get("elec_coeff", ""), base.elec_coeff)
    base.packing_unit_price = _to_float(
        row.get("packing_unit_price", ""), base.packing_unit_price
    )
    base.packing_lot = _to_float(row.get("packing_lot", ""), base.packing_lot)
    base.lot_size = _to_float(row.get("lot_size", ""), base.lot_size)
    base.transport_distance_km = _to_float(
        row.get("transport_distance_km", ""), base.transport_distance_km
    )
    base.transport_per_unit = _to_float_or_none(row.get("transport_per_unit", ""))
    base.material_coeff_default = _to_float(
        row.get("material_coeff_default", ""), base.material_coeff_default
    )
    base.material_coeffs = [
        _to_float_or_none(row.get(f"material_coeff_{i}", "")) for i in range(1, 5)
    ]
    return base


def load_market_prices(material_name: str) -> pd.DataFrame:
    """指定成分の市況推移(月次)を DataFrame で返す。

    Columns: year_month (datetime), price_jpy_per_kg (float)
    """
    if not MARKET_PRICES_CSV_PATH.exists():
        return pd.DataFrame()
    df = pd.read_csv(MARKET_PRICES_CSV_PATH, dtype=str).fillna("")
    df = df[df["material_name"] == material_name].copy()
    if df.empty:
        return df
    df["year_month"] = pd.to_datetime(df["year_month"], format="%Y-%m", errors="coerce")
    df["price_jpy_per_kg"] = pd.to_numeric(df["price_jpy_per_kg"], errors="coerce")
    return df.dropna().sort_values("year_month").reset_index(drop=True)
