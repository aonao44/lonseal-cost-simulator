"""原価シミュレーター Streamlit UI。"""
from __future__ import annotations

import pandas as pd
import streamlit as st

from simulator.calc import (
    CostBreakdown,
    calc_total_cost,
)
from simulator.config import (
    FUEL_COEFF,
    FUEL_USAGE_ELEC_KWH_PER_M,
    FUEL_USAGE_LNG_L_PER_M,
    LOT_SIZE_M,
    MATERIAL_COEFF,
    PACKING_UNIT_PRICE,
    PRODUCT_WEIGHT_KG_PER_M,
)
from simulator.data import get_product_data, get_product_names


def run_app() -> None:
    st.set_page_config(
        page_title="原材料価格交渉シミュレーター",
        layout="wide",
        initial_sidebar_state="collapsed",
    )
    st.title("原材料価格交渉シミュレーター")
    st.caption("PoC — Streamlit")

    product_names = get_product_names()
    if not product_names:
        st.error("品目データが見つかりません。unified.csv を確認してください。")
        return

    selected = st.selectbox("品目を選択", product_names)
    if not selected:
        return

    product_df = get_product_data(selected)
    if product_df.empty:
        st.warning("この品目のデータがありません。")
        return

    _render_product_info(product_df)
    breakdowns = _compute_breakdowns(product_df)
    _render_cost_table(product_df, breakdowns)
    _render_chart(product_df, breakdowns)
    _render_revision_history(product_df)
    _render_proposal_section(product_df, breakdowns)


def _parse_ratio(value: str) -> float:
    """'78%' や '65%' のような文字列を 0.78 に変換。範囲表記は中間値。"""
    value = value.strip().replace("%", "").replace("％", "")
    if not value:
        return 0.0
    if "-" in value and not value.startswith("-"):
        parts = value.split("-")
        try:
            return (float(parts[0]) + float(parts[1])) / 2 / 100
        except (ValueError, IndexError):
            return 0.0
    try:
        v = float(value.lstrip(">").lstrip("<"))
        return v / 100
    except ValueError:
        return 0.0


def _parse_float(value: str) -> float:
    """数値文字列をパース。空文字やパース不能なら 0.0。"""
    value = value.strip()
    if not value:
        return 0.0
    try:
        return float(value)
    except ValueError:
        return 0.0


def _extract_components(row: pd.Series) -> list[dict]:
    """1行から成分リスト（名前・含有量・市況単価）を抽出。"""
    components = []
    for i in range(1, 5):
        name = str(row.get(f"成分{i}", "")).strip()
        ratio = _parse_ratio(str(row.get(f"成分{i}_含有量", "")))
        price = _parse_float(str(row.get(f"［成分{i}］市況単価", "")))
        if name and ratio > 0 and price > 0:
            components.append({"name": name, "ratio": ratio, "market_price": price})
    return components


def _extract_fuels(row: pd.Series) -> list[dict]:
    """1行から燃動力リストを抽出。"""
    fuels = []
    fuel_usages = {
        1: FUEL_USAGE_LNG_L_PER_M,
        2: FUEL_USAGE_ELEC_KWH_PER_M,
    }
    for i in range(1, 3):
        name = str(row.get(f"燃動力{i}", "")).strip()
        price = _parse_float(str(row.get(f"［燃動力{i}］単価", "")))
        usage = fuel_usages[i]
        if name and price > 0:
            fuels.append({"name": name, "usage": usage, "price": price})
    return fuels


def _compute_breakdowns(product_df: pd.DataFrame) -> list[CostBreakdown]:
    """全改定行の原価内訳を計算。"""
    breakdowns = []
    for _, row in product_df.iterrows():
        components = _extract_components(row)
        fuels = _extract_fuels(row)
        hourly_wage = _parse_float(str(row.get("労務費（時間当り）", "")))
        fare_per_m = _parse_float(str(row.get("［運賃］円/m", "")))
        transport_per_truck = fare_per_m * LOT_SIZE_M

        breakdown = calc_total_cost(
            components=components,
            fuels=fuels,
            hourly_wage=hourly_wage,
            packing_price=PACKING_UNIT_PRICE,
            transport_per_truck=transport_per_truck,
        )
        breakdowns.append(breakdown)
    return breakdowns


def _render_product_info(product_df: pd.DataFrame) -> None:
    """品目基本情報セクション。"""
    st.markdown("---")
    st.subheader("品目情報")
    latest = product_df.iloc[-1]
    cols = st.columns(5)
    cols[0].metric("品名", str(latest.get("品名", "")))
    cols[1].metric("文書番号", str(latest.get("文書番号", "")))
    price = _parse_float(str(latest.get("改定後の価格", "")))
    cols[2].metric("現行価格", f"{price:.2f} 円/m" if price else "—")
    cols[3].metric("最終改定日", str(latest.get("改定時期", "")))
    cols[4].metric("製品重量", f"{PRODUCT_WEIGHT_KG_PER_M} kg/m")


def _render_cost_table(
    product_df: pd.DataFrame, breakdowns: list[CostBreakdown]
) -> None:
    """原価内訳テーブル（改定日ごとの時系列）。"""
    st.markdown("---")
    st.subheader("原価内訳（時系列比較）")

    dates = product_df["改定時期"].tolist()
    purchase_prices = [
        _parse_float(str(row.get("改定後の価格", "")))
        for _, row in product_df.iterrows()
    ]

    rows_data: list[dict] = []

    # ① 材料費（成分別明細）
    for i in range(1, 5):
        comp_names: set[str] = set()
        for _, row in product_df.iterrows():
            name = str(row.get(f"成分{i}", "")).strip()
            if name:
                comp_names.add(name)
        if not comp_names:
            continue
        comp_label = f"  成分{i}: {next(iter(comp_names))}"
        row_dict: dict = {"費目": comp_label}
        for j, (_, row) in enumerate(product_df.iterrows()):
            ratio = _parse_ratio(str(row.get(f"成分{i}_含有量", "")))
            price = _parse_float(str(row.get(f"［成分{i}］市況単価", "")))
            if ratio > 0 and price > 0:
                cost = PRODUCT_WEIGHT_KG_PER_M * ratio * price * MATERIAL_COEFF
                row_dict[dates[j]] = f"{cost:.3f}"
            else:
                row_dict[dates[j]] = "—"
        rows_data.append(row_dict)

    material_row: dict = {"費目": "① 材料費 小計"}
    for j, bd in enumerate(breakdowns):
        material_row[dates[j]] = f"{bd.material:.3f}"
    rows_data.append(material_row)

    # ② 燃動力費
    for i in range(1, 3):
        fuel_names: set[str] = set()
        for _, row in product_df.iterrows():
            name = str(row.get(f"燃動力{i}", "")).strip()
            if name:
                fuel_names.add(name)
        if not fuel_names:
            continue
        fuel_label = f"  燃動力{i}: {next(iter(fuel_names))}"
        row_dict = {"費目": fuel_label}
        usage = [FUEL_USAGE_LNG_L_PER_M, FUEL_USAGE_ELEC_KWH_PER_M][i - 1]
        for j, (_, row) in enumerate(product_df.iterrows()):
            price = _parse_float(str(row.get(f"［燃動力{i}］単価", "")))
            if price > 0:
                cost = usage * price * FUEL_COEFF
                row_dict[dates[j]] = f"{cost:.3f}"
            else:
                row_dict[dates[j]] = "—"
        rows_data.append(row_dict)

    fuel_row: dict = {"費目": "② 燃動力費 小計"}
    for j, bd in enumerate(breakdowns):
        fuel_row[dates[j]] = f"{bd.fuel:.3f}"
    rows_data.append(fuel_row)

    labor_row: dict = {"費目": "③ 労務費"}
    for j, bd in enumerate(breakdowns):
        labor_row[dates[j]] = f"{bd.labor:.3f}"
    rows_data.append(labor_row)

    packing_row: dict = {"費目": "④ その他（梱包費）"}
    for j, bd in enumerate(breakdowns):
        packing_row[dates[j]] = f"{bd.packing:.3f}"
    rows_data.append(packing_row)

    transport_row: dict = {"費目": "⑤ 運賃"}
    for j, bd in enumerate(breakdowns):
        transport_row[dates[j]] = f"{bd.transport:.4f}"
    rows_data.append(transport_row)

    total_row: dict = {"費目": "推定原価"}
    for j, bd in enumerate(breakdowns):
        total_row[dates[j]] = f"{bd.total:.2f}"
    rows_data.append(total_row)

    purchase_row: dict = {"費目": "当社購入価格"}
    for j, price in enumerate(purchase_prices):
        purchase_row[dates[j]] = f"{price:.2f}" if price else "—"
    rows_data.append(purchase_row)

    rate_row: dict = {"費目": "製造原価率"}
    for j, (bd, price) in enumerate(zip(breakdowns, purchase_prices)):
        if price > 0:
            rate = bd.total / price * 100
            rate_row[dates[j]] = f"{rate:.0f}%"
        else:
            rate_row[dates[j]] = "—"
    rows_data.append(rate_row)

    table_df = pd.DataFrame(rows_data).set_index("費目")
    st.dataframe(table_df, use_container_width=True)


def _render_chart(
    product_df: pd.DataFrame, breakdowns: list[CostBreakdown]
) -> None:
    """推定原価 vs 当社購入価格の折れ線チャート。"""
    st.markdown("---")
    st.subheader("推定原価 vs 当社購入価格")

    dates = pd.to_datetime(product_df["改定時期"], format="%Y/%m/%d", errors="coerce")
    purchase_prices = [
        _parse_float(str(row.get("改定後の価格", "")))
        for _, row in product_df.iterrows()
    ]

    chart_df = pd.DataFrame(
        {
            "改定日": dates,
            "推定原価（円/m）": [bd.total for bd in breakdowns],
            "当社購入価格（円/m）": purchase_prices,
        }
    ).set_index("改定日")

    st.line_chart(chart_df)


def _render_revision_history(product_df: pd.DataFrame) -> None:
    """改定履歴テーブル。"""
    st.markdown("---")
    st.subheader("改定履歴")

    history = product_df[["改定時期", "元価格", "改定後の価格", "改定理由"]].copy()
    history.columns = ["改定日", "改定前（円/m）", "改定後（円/m）", "改定理由"]
    history = history.reset_index(drop=True)
    st.dataframe(history, use_container_width=True, hide_index=True)


def _build_proposal_text(
    product_df: pd.DataFrame, breakdowns: list[CostBreakdown]
) -> str:
    """シミュレーション結果から交渉用提案文を生成（デモ）。"""
    latest = product_df.iloc[-1]
    bd = breakdowns[-1]
    product_name = str(latest.get("品名", ""))
    supplier = str(latest.get("仕入先", "（仕入先名）"))
    revision_date = str(latest.get("改定時期", ""))
    current_price = _parse_float(str(latest.get("改定後の価格", "")))
    reason = str(latest.get("改定理由", ""))

    cost_rate = (bd.total / current_price * 100) if current_price > 0 else 0

    # 前回改定との差分
    if len(breakdowns) >= 2:
        prev_bd = breakdowns[-2]
        prev_price = _parse_float(
            str(product_df.iloc[-2].get("改定後の価格", ""))
        )
        price_change = current_price - prev_price
        cost_change = bd.total - prev_bd.total
    else:
        price_change = 0.0
        cost_change = 0.0

    lines = [
        f"# {product_name} — 価格改定に関するご提案",
        "",
        f"**対象品目:** {product_name}",
        f"**仕入先:** {supplier}",
        f"**直近改定日:** {revision_date}",
        "",
        "---",
        "",
        "## 1. 現状の分析",
        "",
        f"当社シミュレーションによる推定製造原価は **{bd.total:.2f} 円/m** です。"
        f"現行の当社購入価格 **{current_price:.2f} 円/m** に対し、"
        f"製造原価率は **{cost_rate:.0f}%** と試算されます。",
        "",
        "| 費目 | 金額（円/m） |",
        "|------|------------|",
        f"| 材料費 | {bd.material:.3f} |",
        f"| 燃動力費 | {bd.fuel:.3f} |",
        f"| 労務費 | {bd.labor:.3f} |",
        f"| 梱包費 | {bd.packing:.3f} |",
        f"| 運賃 | {bd.transport:.4f} |",
        f"| **推定原価合計** | **{bd.total:.2f}** |",
        "",
    ]

    if reason:
        lines += [
            "## 2. 仕入先からの改定理由",
            "",
            f"> {reason}",
            "",
        ]

    if price_change != 0:
        direction = "値上げ" if price_change > 0 else "値下げ"
        lines += [
            "## 3. 前回改定との比較",
            "",
            f"- 購入価格変動: {price_change:+.2f} 円/m（{direction}）",
            f"- 推定原価変動: {cost_change:+.2f} 円/m",
            "",
        ]

    # 交渉方針（デモ用固定ロジック）
    lines += [
        "## 4. 交渉方針（案）",
        "",
    ]
    if cost_rate < 70:
        lines += [
            "推定原価率が70%を下回っており、仕入先の利益率に余裕があると見られます。",
            "**現行価格の据え置き、または値下げ交渉の余地があります。**",
            "",
            "### 提案アクション",
            "- 市況データを提示し、原材料費の低下傾向を根拠に価格見直しを要請",
            "- 目標価格: 現行比 **3〜5% 減**",
        ]
    elif cost_rate < 85:
        lines += [
            "推定原価率は適正範囲内です。",
            "値上げ要請があった場合、**原材料費の変動分のみ受け入れる**方針が妥当です。",
            "",
            "### 提案アクション",
            "- 成分別の市況単価推移を確認し、実際の原価上昇幅を精査",
            "- 値上げ幅の上限: 原価上昇分 × 50% を目安に交渉",
        ]
    else:
        lines += [
            "推定原価率が85%を超えており、仕入先の利益圧迫が推測されます。",
            "**一定の値上げ受け入れはやむを得ない**と判断されますが、"
            "段階的な価格改定を提案します。",
            "",
            "### 提案アクション",
            "- 値上げ幅を2回に分割し、半年ごとの段階改定を提案",
            "- 長期契約（1年以上）を条件に値上げ幅の圧縮を交渉",
        ]

    lines += [
        "",
        "---",
        "",
        "*本提案文はシミュレーション結果に基づくデモ出力です。"
        "実際の交渉にあたっては、最新の市況データおよび社内方針をご確認ください。*",
    ]
    return "\n".join(lines)


def _render_proposal_section(
    product_df: pd.DataFrame, breakdowns: list[CostBreakdown]
) -> None:
    """提案文作成セクション。"""
    st.markdown("---")
    st.subheader("提案文作成")

    if st.button("提案文を作成", type="primary", use_container_width=True):
        with st.spinner("提案文を生成中..."):
            proposal = _build_proposal_text(product_df, breakdowns)
        st.session_state["proposal_text"] = proposal

    if "proposal_text" in st.session_state:
        st.markdown(st.session_state["proposal_text"])
        st.download_button(
            label="提案文をダウンロード（Markdown）",
            data=st.session_state["proposal_text"],
            file_name="proposal.md",
            mime="text/markdown",
        )
