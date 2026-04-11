"""原価計算ロジック。"""
from __future__ import annotations

from dataclasses import dataclass

from simulator.config import (
    FUEL_COEFF,
    LABOR_COEFF,
    LOT_SIZE_M,
    MATERIAL_COEFF,
    PACKING_LOT,
    PRODUCT_WEIGHT_KG_PER_M,
    PRODUCTION_TIME_H_PER_M,
)


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


def calc_material_cost(components: list[dict]) -> float:
    """材料費 = Σ(製品重量 × 成分割合 × 市況単価 × 係数)"""
    total = 0.0
    for comp in components:
        ratio = comp["ratio"]
        price = comp["market_price"]
        total += PRODUCT_WEIGHT_KG_PER_M * ratio * price * MATERIAL_COEFF
    return total


def calc_fuel_cost(fuels: list[dict]) -> float:
    """燃動力費 = Σ(使用量 × 単価 × 係数)"""
    total = 0.0
    for fuel in fuels:
        total += fuel["usage"] * fuel["price"] * FUEL_COEFF
    return total


def calc_labor_cost(hourly_wage: float) -> float:
    """労務費 = 推定生産時間 × 時間単価 × 係数"""
    return PRODUCTION_TIME_H_PER_M * hourly_wage * LABOR_COEFF


def calc_packing_cost(packing_price: float) -> float:
    """梱包費 = 梱包単価 × 梱包ロット / ロットサイズ"""
    return packing_price * PACKING_LOT / LOT_SIZE_M


def calc_transport_cost(transport_per_truck: float) -> float:
    """運賃 = 運賃(円/台) / ロットサイズ(m)"""
    return transport_per_truck / LOT_SIZE_M


def calc_total_cost(
    components: list[dict],
    fuels: list[dict],
    hourly_wage: float,
    packing_price: float,
    transport_per_truck: float,
) -> CostBreakdown:
    """全費目を計算して CostBreakdown を返す。"""
    return CostBreakdown(
        material=calc_material_cost(components),
        fuel=calc_fuel_cost(fuels),
        labor=calc_labor_cost(hourly_wage),
        packing=calc_packing_cost(packing_price),
        transport=calc_transport_cost(transport_per_truck),
    )
