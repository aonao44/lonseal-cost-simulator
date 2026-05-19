"""原価計算ロジック。

品目別係数 (ItemCoeffs) を引数で受け取る。`load_item_coeffs()` が item_overrides.csv
を参照し、行が無ければ config.py のデフォルト値で ItemCoeffs を生成する。
"""
from __future__ import annotations

from dataclasses import dataclass, field

from simulator.config import (
    FUEL_COEFF,
    FUEL_USAGE_ELEC_KWH_PER_M,
    FUEL_USAGE_LNG_L_PER_M,
    LABOR_COEFF,
    LOT_SIZE_M,
    MATERIAL_COEFF,
    PACKING_LOT,
    PACKING_UNIT_PRICE,
    PRODUCT_WEIGHT_KG_PER_M,
    PRODUCTION_TIME_H_PER_M,
)


@dataclass
class ItemCoeffs:
    """品目別の係数・物量パラメータ。"""

    unit: str = "円/m"
    product_weight_per_unit: float = PRODUCT_WEIGHT_KG_PER_M
    production_time_h_per_unit: float = PRODUCTION_TIME_H_PER_M
    labor_coeff: float = LABOR_COEFF
    lng_usage: float = FUEL_USAGE_LNG_L_PER_M
    lng_coeff: float = FUEL_COEFF
    elec_usage: float = FUEL_USAGE_ELEC_KWH_PER_M
    elec_coeff: float = FUEL_COEFF
    packing_unit_price: float = PACKING_UNIT_PRICE
    packing_lot: float = PACKING_LOT
    lot_size: float = LOT_SIZE_M
    transport_distance_km: float = 0.0
    # 運賃の品目単位値（円/m or 円/kg 等）。None なら unified.csv の値にフォールバック
    transport_per_unit: float | None = None
    material_coeff_default: float = MATERIAL_COEFF
    # 成分別係数(成分1-4)。None ならデフォルトを使用。
    material_coeffs: list[float | None] = field(
        default_factory=lambda: [None, None, None, None]
    )

    def coeff_for_component(self, idx_1based: int) -> float:
        """成分インデックス(1始まり)に対応する係数を返す。"""
        if 1 <= idx_1based <= len(self.material_coeffs):
            v = self.material_coeffs[idx_1based - 1]
            if v is not None:
                return v
        return self.material_coeff_default


@dataclass
class CostBreakdown:
    """原価内訳。"""

    material: float
    fuel: float
    labor: float
    packing: float
    transport: float

    @property
    def total(self) -> float:
        return self.material + self.fuel + self.labor + self.packing + self.transport


def calc_material_cost(components: list[dict], coeffs: ItemCoeffs) -> float:
    """材料費 = Σ(製品重量 × 成分割合 × 市況単価 × 成分別係数)"""
    total = 0.0
    for comp in components:
        ratio = comp["ratio"]
        price = comp["market_price"]
        idx = comp.get("index", 1)
        c = coeffs.coeff_for_component(idx)
        total += coeffs.product_weight_per_unit * ratio * price * c
    return total


def calc_fuel_cost(fuels: list[dict], coeffs: ItemCoeffs) -> float:
    """燃動力費 = Σ(使用量 × 単価 × 燃動力別係数)"""
    total = 0.0
    for fuel in fuels:
        total += fuel["usage"] * fuel["price"] * fuel["coeff"]
    return total


def calc_labor_cost(hourly_wage: float, coeffs: ItemCoeffs) -> float:
    """労務費 = 推定生産時間 × 時間単価 × 係数"""
    return coeffs.production_time_h_per_unit * hourly_wage * coeffs.labor_coeff


def calc_packing_cost(coeffs: ItemCoeffs) -> float:
    """梱包費 = 梱包単価 × 梱包ロット / ロットサイズ"""
    if coeffs.lot_size <= 0:
        return 0.0
    return coeffs.packing_unit_price * coeffs.packing_lot / coeffs.lot_size


def calc_transport_cost(transport_per_truck: float, coeffs: ItemCoeffs) -> float:
    """運賃 = 運賃(円/台) / ロットサイズ"""
    if coeffs.lot_size <= 0:
        return 0.0
    return transport_per_truck / coeffs.lot_size


def calc_total_cost(
    components: list[dict],
    fuels: list[dict],
    hourly_wage: float,
    transport_per_truck: float,
    coeffs: ItemCoeffs,
) -> CostBreakdown:
    """全費目を計算して CostBreakdown を返す。"""
    return CostBreakdown(
        material=calc_material_cost(components, coeffs),
        fuel=calc_fuel_cost(fuels, coeffs),
        labor=calc_labor_cost(hourly_wage, coeffs),
        packing=calc_packing_cost(coeffs),
        transport=calc_transport_cost(transport_per_truck, coeffs),
    )
