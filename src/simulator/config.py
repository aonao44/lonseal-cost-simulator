"""原価シミュレーターの定数・パス定義。"""
from __future__ import annotations

from pathlib import Path

# --- パス ---
ROOT_DIR = Path(__file__).resolve().parents[2]
DATA_DIR = ROOT_DIR / "data"
UNIFIED_CSV_PATH = DATA_DIR / "master" / "unified.csv"
ITEM_OVERRIDES_CSV_PATH = DATA_DIR / "master" / "item_overrides.csv"
MARKET_PRICES_CSV_PATH = DATA_DIR / "master" / "market_prices.csv"

# --- 原価計算のデフォルト係数（item_overrides.csv で品目別に上書き可能） ---
MATERIAL_COEFF = 0.4
FUEL_COEFF = 0.03
LABOR_COEFF = 0.00045
PRODUCT_WEIGHT_KG_PER_M = 0.08
PRODUCTION_TIME_H_PER_M = 4.0
PACKING_LOT = 300
PACKING_UNIT_PRICE = 135.0
FUEL_USAGE_LNG_L_PER_M = 0.5
FUEL_USAGE_ELEC_KWH_PER_M = 0.5
LOT_SIZE_M = 128_000
