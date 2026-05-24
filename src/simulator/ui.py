"""原価シミュレーター Streamlit UI。"""
from __future__ import annotations

from html import escape as html_escape

import altair as alt
import pandas as pd
import streamlit as st

from simulator.calc import (
    CostBreakdown,
    ItemCoeffs,
    calc_total_cost,
)
from simulator.data import (
    get_product_data,
    get_product_names,
    load_item_coeffs,
    load_market_prices,
)


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

    doc_no = str(product_df.iloc[-1].get("文書番号", "")).strip()
    coeffs = load_item_coeffs(doc_no)

    _render_product_info(product_df, coeffs)
    breakdowns = _compute_breakdowns(product_df, coeffs)
    _render_cost_table(product_df, breakdowns, coeffs)
    _render_chart(product_df, breakdowns, coeffs)
    _render_revision_history(product_df, coeffs)
    _render_source_links(product_df)
    _render_proposal_section(product_df, breakdowns, coeffs)


def _parse_ratio(value: str) -> float:
    """'78%' や '65%' のような文字列を 0.78 に変換。範囲表記は中間値。"""
    value = value.strip().replace("%", "").replace("％", "").lstrip("約")
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
    """1行から成分リスト（名前・含有量・市況単価・index）を抽出。"""
    components = []
    for i in range(1, 5):
        name = str(row.get(f"成分{i}", "")).strip()
        ratio = _parse_ratio(str(row.get(f"成分{i}_含有量", "")))
        price = _parse_float(str(row.get(f"［成分{i}］市況単価", "")))
        if name and ratio > 0 and price > 0:
            components.append(
                {"name": name, "ratio": ratio, "market_price": price, "index": i}
            )
    return components


def _extract_fuels(row: pd.Series, coeffs: ItemCoeffs) -> list[dict]:
    """1行から燃動力リストを抽出。係数・使用量は coeffs から。"""
    fuels = []
    fuel_meta = {
        1: ("LNG", coeffs.lng_usage, coeffs.lng_coeff),
        2: ("電力", coeffs.elec_usage, coeffs.elec_coeff),
    }
    for i in (1, 2):
        name = str(row.get(f"燃動力{i}", "")).strip()
        price = _parse_float(str(row.get(f"［燃動力{i}］単価", "")))
        _, usage, c = fuel_meta[i]
        if name and price > 0:
            fuels.append(
                {"name": name, "usage": usage, "price": price, "coeff": c, "index": i}
            )
    return fuels


def _compute_breakdowns(
    product_df: pd.DataFrame, coeffs: ItemCoeffs
) -> list[CostBreakdown]:
    """全改定行の原価内訳を計算。"""
    breakdowns: list[CostBreakdown] = []
    for _, row in product_df.iterrows():
        components = _extract_components(row)
        fuels = _extract_fuels(row, coeffs)
        hourly_wage = _parse_float(str(row.get("労務費（時間当り）", "")))
        # 運賃はオーバーライドがあればそれを優先、無ければ unified.csv の ［運賃］円/m を使用
        if coeffs.transport_per_unit is not None:
            fare_per_unit = coeffs.transport_per_unit
        else:
            fare_per_unit = _parse_float(str(row.get("［運賃］円/m", "")))
        transport_per_truck = fare_per_unit * coeffs.lot_size

        breakdown = calc_total_cost(
            components=components,
            fuels=fuels,
            hourly_wage=hourly_wage,
            transport_per_truck=transport_per_truck,
            coeffs=coeffs,
        )
        breakdowns.append(breakdown)
    return breakdowns


def _render_product_info(product_df: pd.DataFrame, coeffs: ItemCoeffs) -> None:
    """品目基本情報セクション。"""
    st.markdown("---")
    st.subheader("品目情報")
    st.caption("選択した品目の基本情報です。品質仕様書・単価改定履歴から抽出しています。")
    latest = product_df.iloc[-1]
    price = _parse_float(str(latest.get("改定後の価格", "")))
    weight_unit = "kg/m" if coeffs.unit.endswith("/m") else "kg"

    # 品名は metric だと長い文字列で切れるため markdown で全幅表示
    # unified.csv 由来の外部入力なので XSS 対策として html.escape を必ず通す
    product_name = str(latest.get("品名", ""))
    st.markdown(
        f"<div style='font-size:0.85rem;color:#7a8290;margin-bottom:0.1rem;'>品名</div>"
        f"<div style='font-size:1.35rem;font-weight:600;line-height:1.35;"
        f"word-break:break-word;margin-bottom:0.5rem;'>{html_escape(product_name)}</div>",
        unsafe_allow_html=True,
    )

    cols = st.columns(4)
    cols[0].metric("文書番号", str(latest.get("文書番号", "")))
    cols[1].metric("現行価格", f"{price:.2f} {coeffs.unit}" if price else "—")
    cols[2].metric("最終改定日", str(latest.get("改定時期", "")))
    cols[3].metric("製品重量", f"{coeffs.product_weight_per_unit} {weight_unit}")


def _render_market_chart(component_name: str) -> None:
    """成分の市況推移チャートを描画。データが無ければ案内を出す。"""
    df = load_market_prices(component_name)
    if df.empty:
        st.info(f"『{component_name}』の市況時系列データは未登録です（market_prices.csv に追加してください）。")
        return
    chart_df = df[["year_month", "price_jpy_per_kg"]].rename(
        columns={"year_month": "年月", "price_jpy_per_kg": "JPY/kg"}
    )
    chart = (
        alt.Chart(chart_df)
        .mark_line(point=True)
        .encode(
            x=alt.X("年月:T", axis=alt.Axis(title="年月", format="%Y-%m")),
            y=alt.Y(
                "JPY/kg:Q",
                axis=alt.Axis(title="JPY/kg"),
                scale=alt.Scale(zero=False, reverse=False),
                sort="ascending",
            ),
            tooltip=[
                alt.Tooltip("年月:T", format="%Y-%m"),
                alt.Tooltip("JPY/kg:Q", format=".2f"),
            ],
        )
        .properties(height=240)
    )
    st.altair_chart(chart, use_container_width=True)
    latest = df.iloc[-1]
    st.caption(
        f"最新: {latest['year_month'].strftime('%Y-%m')} 時点 {latest['price_jpy_per_kg']:.2f} 円/kg"
        f"（{df['year_month'].min().strftime('%Y-%m')}〜{df['year_month'].max().strftime('%Y-%m')}）"
    )


def _render_cost_table(
    product_df: pd.DataFrame,
    breakdowns: list[CostBreakdown],
    coeffs: ItemCoeffs,
) -> None:
    """原価内訳セクション。費目ごとに expander で計算詳細を展開可能。"""
    st.markdown("---")
    st.subheader(f"原価内訳（時系列比較）（{coeffs.unit}）")
    st.caption(
        "成分・燃動力・労務費・運賃から推定原価を積み上げ計算し、改定日ごとに比較します。"
        "各費目を展開すると「市況単価 × 推定使用量 × 係数 = 推定費用」の内訳を確認できます。"
    )
    st.info(
        "市況単価は日銀企業物価指数（CGPI）、労務費は厚労省最低賃金、運賃は国交省標準運賃に基づく推計値です。"
        " 詳細は[こちら](https://axiomatic-eoraptor-b67.notion.site/v2-36a57afb2a398149b8c4e899708f2b98)を参照。"
    )

    dates = product_df["改定時期"].tolist()
    purchase_prices = [
        _parse_float(str(row.get("改定後の価格", "")))
        for _, row in product_df.iterrows()
    ]

    # --- ① 材料費 ---
    st.markdown("### ① 材料費")
    for i in range(1, 5):
        comp_names = {
            str(row.get(f"成分{i}", "")).strip()
            for _, row in product_df.iterrows()
            if str(row.get(f"成分{i}", "")).strip()
        }
        if not comp_names:
            continue
        comp_name = next(iter(comp_names))
        # 成分別の係数（オーバーライドあり/無し）
        coeff_val = coeffs.coeff_for_component(i)
        with st.expander(f"成分{i}: {comp_name}（係数 {coeff_val}）", expanded=False):
            tab_calc, tab_market = st.tabs(["計算内訳", "市況推移"])
            with tab_calc:
                rows = []
                for j, (_, row) in enumerate(product_df.iterrows()):
                    ratio = _parse_ratio(str(row.get(f"成分{i}_含有量", "")))
                    price = _parse_float(str(row.get(f"［成分{i}］市況単価", "")))
                    if ratio > 0 and price > 0:
                        cost = (
                            coeffs.product_weight_per_unit * ratio * price * coeff_val
                        )
                        rows.append(
                            {
                                "改定日": dates[j],
                                "製品重量": coeffs.product_weight_per_unit,
                                "成分割合": f"{ratio*100:.1f}%",
                                "市況単価(円/kg)": price,
                                "係数": coeff_val,
                                f"推定費用({coeffs.unit})": round(cost, 4),
                            }
                        )
                if rows:
                    st.dataframe(pd.DataFrame(rows), hide_index=True, use_container_width=True)
                else:
                    st.caption("有効なデータがありません。")
            with tab_market:
                _render_market_chart(comp_name)

    # 材料費 小計表
    material_summary = pd.DataFrame(
        [{"改定日": dates[j], f"材料費 小計({coeffs.unit})": round(bd.material, 3)} for j, bd in enumerate(breakdowns)]
    )
    st.markdown("**材料費 小計**")
    st.dataframe(material_summary, hide_index=True, use_container_width=True)

    # --- ② 燃動力費 ---
    st.markdown("### ② 燃動力費")
    fuel_meta = {1: ("LNG", coeffs.lng_usage, coeffs.lng_coeff),
                 2: ("電力", coeffs.elec_usage, coeffs.elec_coeff)}
    for i in (1, 2):
        fuel_names = {
            str(row.get(f"燃動力{i}", "")).strip()
            for _, row in product_df.iterrows()
            if str(row.get(f"燃動力{i}", "")).strip()
        }
        if not fuel_names:
            continue
        fuel_label, usage, c = fuel_meta[i]
        display_name = next(iter(fuel_names))
        with st.expander(f"燃動力{i}: {display_name}（使用量 {usage}, 係数 {c}）", expanded=False):
            rows = []
            for j, (_, row) in enumerate(product_df.iterrows()):
                price = _parse_float(str(row.get(f"［燃動力{i}］単価", "")))
                if price > 0:
                    cost = usage * price * c
                    rows.append(
                        {
                            "改定日": dates[j],
                            "使用量": usage,
                            "単価": price,
                            "係数": c,
                            f"推定費用({coeffs.unit})": round(cost, 4),
                        }
                    )
            if rows:
                st.dataframe(pd.DataFrame(rows), hide_index=True, use_container_width=True)
            else:
                st.caption("有効なデータがありません。")

    fuel_summary = pd.DataFrame(
        [{"改定日": dates[j], f"燃動力費 小計({coeffs.unit})": round(bd.fuel, 3)} for j, bd in enumerate(breakdowns)]
    )
    st.markdown("**燃動力費 小計**")
    st.dataframe(fuel_summary, hide_index=True, use_container_width=True)

    # --- ③ 労務費 ---
    st.markdown("### ③ 労務費")
    with st.expander(
        f"労務費（生産時間 {coeffs.production_time_h_per_unit} h, 係数 {coeffs.labor_coeff}）",
        expanded=False,
    ):
        rows = []
        for j, (_, row) in enumerate(product_df.iterrows()):
            wage = _parse_float(str(row.get("労務費（時間当り）", "")))
            cost = coeffs.production_time_h_per_unit * wage * coeffs.labor_coeff
            rows.append(
                {
                    "改定日": dates[j],
                    "生産時間(h)": coeffs.production_time_h_per_unit,
                    "時間単価(円/h)": wage,
                    "係数": coeffs.labor_coeff,
                    f"推定費用({coeffs.unit})": round(cost, 4),
                }
            )
        st.dataframe(pd.DataFrame(rows), hide_index=True, use_container_width=True)

    # --- ④ 梱包費 ---
    st.markdown("### ④ 梱包費")
    with st.expander(
        f"梱包費（単価 {coeffs.packing_unit_price} 円 × ロット {coeffs.packing_lot} ÷ LOT {coeffs.lot_size}）",
        expanded=False,
    ):
        cost = (
            coeffs.packing_unit_price * coeffs.packing_lot / coeffs.lot_size
            if coeffs.lot_size
            else 0
        )
        st.caption(f"全改定共通: **{cost:.4f} {coeffs.unit}**")

    # --- ⑤ 運賃 ---
    st.markdown("### ⑤ 運賃")
    transport_source = "item_overrides.csv" if coeffs.transport_per_unit is not None else "unified.csv ［運賃］円/m"
    with st.expander(
        f"運賃（距離 {coeffs.transport_distance_km} km, LOT {coeffs.lot_size}, 出典: {transport_source}）",
        expanded=False,
    ):
        rows = []
        for j, (_, row) in enumerate(product_df.iterrows()):
            if coeffs.transport_per_unit is not None:
                fare_per_unit = coeffs.transport_per_unit
            else:
                fare_per_unit = _parse_float(str(row.get("［運賃］円/m", "")))
            rows.append(
                {
                    "改定日": dates[j],
                    f"運賃({coeffs.unit})": round(fare_per_unit, 4),
                    "LOT": coeffs.lot_size,
                    f"推定費用({coeffs.unit})": round(breakdowns[j].transport, 4),
                }
            )
        st.dataframe(pd.DataFrame(rows), hide_index=True, use_container_width=True)

    # --- サマリ表 ---
    st.markdown("### サマリ")
    summary_rows = []
    for j, bd in enumerate(breakdowns):
        purchase = purchase_prices[j]
        rate = (bd.total / purchase * 100) if purchase > 0 else None
        summary_rows.append(
            {
                "改定日": dates[j],
                f"材料費({coeffs.unit})": round(bd.material, 3),
                f"燃動力費({coeffs.unit})": round(bd.fuel, 3),
                f"労務費({coeffs.unit})": round(bd.labor, 3),
                f"梱包費({coeffs.unit})": round(bd.packing, 3),
                f"運賃({coeffs.unit})": round(bd.transport, 4),
                f"推定原価({coeffs.unit})": round(bd.total, 2),
                f"当社購入価格({coeffs.unit})": round(purchase, 2) if purchase else None,
                "製造原価率(%)": round(rate, 1) if rate is not None else None,
            }
        )
    st.dataframe(pd.DataFrame(summary_rows), hide_index=True, use_container_width=True)


def _render_chart(
    product_df: pd.DataFrame,
    breakdowns: list[CostBreakdown],
    coeffs: ItemCoeffs,
) -> None:
    """推定原価 vs 当社購入価格の折れ線チャート。"""
    st.markdown("---")
    st.subheader("推定原価 vs 当社購入価格")
    st.caption("推定原価と当社購入価格の推移を可視化したチャートです。乖離が大きいほど交渉余地があります。")

    dates = pd.to_datetime(product_df["改定時期"], format="%Y/%m/%d", errors="coerce")
    purchase_prices = [
        _parse_float(str(row.get("改定後の価格", "")))
        for _, row in product_df.iterrows()
    ]

    estimate_col = f"推定原価（{coeffs.unit}）"
    purchase_col = f"当社購入価格（{coeffs.unit}）"
    chart_df = pd.DataFrame(
        {
            "改定日": dates,
            estimate_col: [bd.total for bd in breakdowns],
            purchase_col: purchase_prices,
        }
    )
    long_df = chart_df.melt(
        id_vars=["改定日"], value_vars=[estimate_col, purchase_col],
        var_name="系列", value_name="金額",
    )
    chart = (
        alt.Chart(long_df)
        .mark_line(point=True)
        .encode(
            x=alt.X("改定日:T", axis=alt.Axis(title="改定日", format="%Y-%m")),
            y=alt.Y(
                "金額:Q",
                axis=alt.Axis(title=f"金額（{coeffs.unit}）"),
                scale=alt.Scale(zero=False, reverse=False),
                sort="ascending",
            ),
            color=alt.Color("系列:N", legend=alt.Legend(title=None, orient="top")),
            tooltip=[
                alt.Tooltip("改定日:T", format="%Y-%m-%d"),
                alt.Tooltip("系列:N"),
                alt.Tooltip("金額:Q", format=".2f"),
            ],
        )
        .properties(height=320)
    )
    st.altair_chart(chart, use_container_width=True)


def _render_revision_history(product_df: pd.DataFrame, coeffs: ItemCoeffs) -> None:
    """改定履歴テーブル。"""
    st.markdown("---")
    st.subheader("改定履歴")
    st.caption("過去の価格改定の記録です。改定日・改定前後の価格・仕入先が申告した改定理由を一覧で確認できます。")

    history = product_df[["改定時期", "元価格", "改定後の価格", "改定理由"]].copy()
    history.columns = ["改定日", f"改定前（{coeffs.unit}）", f"改定後（{coeffs.unit}）", "改定理由"]
    history = history.reset_index(drop=True)
    st.dataframe(history, use_container_width=True, hide_index=True)


def _build_proposal_text(
    product_df: pd.DataFrame,
    breakdowns: list[CostBreakdown],
    coeffs: ItemCoeffs,
    *,
    internal: bool = False,
) -> str:
    """シミュレーション結果から交渉用提案文を生成（デモ）。

    internal=True のとき、社内確認用として計算根拠の出典（公式統計URL等）を末尾に付与する。
    """
    latest = product_df.iloc[-1]
    bd = breakdowns[-1]
    product_name = str(latest.get("品名", ""))
    supplier = str(latest.get("仕入先", "（仕入先名）"))
    revision_date = str(latest.get("改定時期", ""))
    current_price = _parse_float(str(latest.get("改定後の価格", "")))
    reason = str(latest.get("改定理由", ""))
    unit = coeffs.unit

    cost_rate = (bd.total / current_price * 100) if current_price > 0 else 0

    if len(breakdowns) >= 2:
        prev_bd = breakdowns[-2]
        prev_price = _parse_float(str(product_df.iloc[-2].get("改定後の価格", "")))
        price_change = current_price - prev_price
        cost_change = bd.total - prev_bd.total
    else:
        price_change = 0.0
        cost_change = 0.0

    title_suffix = "（社内確認用）" if internal else ""
    lines = [
        f"# {product_name} — 価格改定に関するご提案{title_suffix}",
        "",
        f"**対象品目:** {product_name}",
        f"**仕入先:** {supplier}",
        f"**直近改定日:** {revision_date}",
        "",
        "---",
        "",
        "## 1. 現状の分析",
        "",
        f"当社シミュレーションによる推定製造原価は **{bd.total:.2f} {unit}** です。"
        f"現行の当社購入価格 **{current_price:.2f} {unit}** に対し、"
        f"製造原価率は **{cost_rate:.0f}%** と試算されます。",
        "",
        f"| 費目 | 金額（{unit}） |",
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
            f"- 購入価格変動: {price_change:+.2f} {unit}（{direction}）",
            f"- 推定原価変動: {cost_change:+.2f} {unit}",
            "",
        ]

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
            "**一定の値上げ受け入れはやむを得ない**と判断されますが、段階的な価格改定を提案します。",
            "",
            "### 提案アクション",
            "- 値上げ幅を2回に分割し、半年ごとの段階改定を提案",
            "- 長期契約（1年以上）を条件に値上げ幅の圧縮を交渉",
        ]

    if internal:
        lines += ["", "## 5. 計算根拠の出典（社内確認用）", ""]
        lines += _build_source_citation_lines(latest)

    lines += [
        "",
        "---",
        "",
        "*本提案文はシミュレーション結果に基づくデモ出力です。"
        "実際の交渉にあたっては、最新の市況データおよび社内方針をご確認ください。*",
    ]
    return "\n".join(lines)


def _build_source_citation_lines(latest: pd.Series) -> list[str]:
    """社内確認用に、計算根拠（公式統計）の出典リストを返す。

    1) 共通の公式統計（市況・労務費・運賃の算出根拠）
    2) 当該品目の unified.csv に登録された一次ソースURL
    """
    lines = [
        "本提案の推定原価は、以下の公的統計を基準にシミュレーションしています。",
        "",
        "### 共通の算出根拠",
        "",
        "- **材料費（成分市況単価）**: 日銀 企業物価指数（CGPI）／PPI類別 月報",
        "  [https://www.boj.or.jp/statistics/pi/cgpi_release/index.htm/](https://www.boj.or.jp/statistics/pi/cgpi_release/index.htm/)",
        "- **燃動力費（LNG・電力）**: 日銀 CGPI「石油・石炭」「電力・ガス・水道」類別指数",
        "  [https://www.boj.or.jp/statistics/pi/cgpi_release/index.htm/](https://www.boj.or.jp/statistics/pi/cgpi_release/index.htm/)",
        "- **労務費**: 厚生労働省 地域別最低賃金（全国加重平均）",
        "  [https://www.mhlw.go.jp/stf/seisakunitsuite/bunya/koyou_roudou/roudoukijun/minimumichiran/index.html](https://www.mhlw.go.jp/stf/seisakunitsuite/bunya/koyou_roudou/roudoukijun/minimumichiran/index.html)",
        "- **運賃**: 国土交通省 標準的な運賃（令和6年3月告示、大型車10t）",
        "  [https://www.mlit.go.jp/jidosha/jidosha_tk4_000118.html](https://www.mlit.go.jp/jidosha/jidosha_tk4_000118.html)",
        "",
    ]

    # 当該品目に紐付く一次ソースURL（unified.csv 由来）
    item_links: list[tuple[str, str]] = []
    for i in range(1, 5):
        comp_name = str(latest.get(f"成分{i}", "")).strip()
        url = str(latest.get(f"［成分{i}］市況情報", "")).strip()
        if comp_name and url and url.startswith("http"):
            item_links.append((f"成分{i}（{comp_name}）市況単価", url))
    for i in range(1, 5):
        fuel_name = str(latest.get(f"燃動力{i}", "")).strip()
        url = str(latest.get(f"［燃動力{i}］市況情報", "")).strip()
        if fuel_name and url and url.startswith("http"):
            item_links.append((f"燃動力{i}（{fuel_name}）単価", url))
    labor_url = str(latest.get("［労務費］市況情報", "")).strip()
    if labor_url and labor_url.startswith("http"):
        item_links.append(("労務費", labor_url))

    if item_links:
        lines += ["### 当該品目の一次ソース", ""]
        for label, url in item_links:
            lines.append(f"- {label}: [{url}]({url})")
        lines.append("")

    return lines


def _render_source_links(product_df: pd.DataFrame) -> None:
    """一次ソースURL参照セクション。unified.csv の市況情報列からURLを抽出して表示。"""
    st.markdown("---")
    st.subheader("一次ソース参照")
    st.caption("各費目の市況データの出典URLです。クリックすると最新の市況データを確認できます。")

    latest = product_df.iloc[-1]

    links: list[tuple[str, str]] = []

    for i in range(1, 5):
        comp_name = str(latest.get(f"成分{i}", "")).strip()
        url = str(latest.get(f"［成分{i}］市況情報", "")).strip()
        if comp_name and url and url.startswith("http"):
            links.append((f"成分{i}（{comp_name}）市況単価", url))

    for i in range(1, 5):
        fuel_name = str(latest.get(f"燃動力{i}", "")).strip()
        url = str(latest.get(f"［燃動力{i}］市況情報", "")).strip()
        if fuel_name and url and url.startswith("http"):
            links.append((f"燃動力{i}（{fuel_name}）単価", url))

    url = str(latest.get("［労務費］市況情報", "")).strip()
    if url and url.startswith("http"):
        links.append(("労務費", url))

    if not links:
        st.info("この品目の市況情報URLはデータに登録されていません。")
        return

    cols = st.columns(min(len(links), 3))
    for idx, (label, url) in enumerate(links):
        cols[idx % 3].markdown(f"**{label}**  \n[{url}]({url})")


def _render_proposal_section(
    product_df: pd.DataFrame,
    breakdowns: list[CostBreakdown],
    coeffs: ItemCoeffs,
) -> None:
    """提案文作成セクション。"""
    st.markdown("---")
    st.subheader("提案文作成")
    st.caption("シミュレーション結果に基づき、仕入先への価格交渉用の提案文を自動生成します。製造原価率に応じた交渉方針の案を含みます。")
    st.info("提案文は日銀CGPI・厚労省最低賃金・国交省標準運賃ベースのシミュレーション結果に基づきます。")

    mode = st.radio(
        "提案文の用途",
        options=["顧客向け", "社内確認用"],
        index=0,
        horizontal=True,
        help="『社内確認用』では計算根拠（公式統計の出典URL）を本文末尾に付与します。",
        key="proposal_mode",
    )
    internal = mode == "社内確認用"

    if st.button("提案文を作成", type="primary", use_container_width=True):
        with st.spinner("提案文を生成中..."):
            proposal = _build_proposal_text(
                product_df, breakdowns, coeffs, internal=internal
            )
        st.session_state["proposal_text"] = proposal
        st.session_state["proposal_internal"] = internal

    if "proposal_text" in st.session_state:
        saved_internal = st.session_state.get("proposal_internal", False)
        if saved_internal != internal:
            saved_label = "社内確認用" if saved_internal else "顧客向け"
            st.warning(
                f"現在表示中の提案文は『{saved_label}』モードで生成されたものです。"
                f"用途を変更したので、再度『提案文を作成』を押してください。"
            )
        else:
            st.markdown(st.session_state["proposal_text"])
            file_suffix = "_internal" if saved_internal else ""
            st.download_button(
                label="提案文をダウンロード（Markdown）",
                data=st.session_state["proposal_text"],
                file_name=f"proposal{file_suffix}.md",
                mime="text/markdown",
            )
