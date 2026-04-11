"""原価シミュレーターの定数・パス定義。"""
from __future__ import annotations

from pathlib import Path

# --- パス ---
ROOT_DIR = Path(__file__).resolve().parents[2]
DATA_DIR = ROOT_DIR / "data"
UNIFIED_CSV_PATH = DATA_DIR / "master" / "unified.csv"

# --- 原価計算の固定係数 ---
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
