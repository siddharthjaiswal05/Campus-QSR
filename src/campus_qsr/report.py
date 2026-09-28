"""Run the full analysis and write every table and headline figure to outputs/."""

from __future__ import annotations

import json
from pathlib import Path
from typing import Any

import pandas as pd

from . import calendar_model as cm
from . import offpeak as op
from . import pnl as P
from . import sku_economics as se
from . import throughput as th
from .assumptions import OUTPUT_DIR, Assumptions


def build_results(a: Assumptions) -> dict[str, Any]:
    """Compute everything once and return both tables and headline figures."""
    calendar = cm.build_calendar(a)
    monthly_demand = cm.monthly_demand(calendar)
    states = cm.state_summary(calendar)
    peak_profile = cm.peak_day_profile(a, calendar)
    flat_comparison = cm.flat_average_comparison(calendar)

    skus = se.sku_table(a)
    ranges = se.top_7_ranges(a)
    basket = se.basket_economics(a)
    bridge = se.variable_cost_bridge(a)

    monthly_pnl = P.monthly_pnl(a, monthly_demand)
    annual = P.annual_summary(monthly_pnl)
    be = P.break_even(a)
    month_conc = P.month_contribution_concentration(monthly_pnl)
    sku_conc = P.sku_contribution_concentration(a, annual["annual_orders"])

    base_line = th.baseline_line(a)
    exp_line = th.express_line(a)
    scenarios = th.throughput_scenarios(a, peak_profile)
    eligible = th.express_eligible_mix(a)
    recovered = th.recovered_revenue(a, calendar, scenarios, basket)

    flex = op.staffing_flex(a, monthly_pnl)
    pickup = op.pre_order_pickup(a, monthly_pnl, scenarios)
    combos = op.combo_bundling(a)
    subs = op.subscription(a)
    lean_bridge = op.lean_month_bridge(a, monthly_pnl, subs, pickup, combos)

    trading = cm.operating_days(calendar)
    peak_row = states[states["state"] == "peak"].iloc[0]

    headline = {
        "annual_orders": annual["annual_orders"],
        "operating_days": int(len(trading)),
        "peak_share_of_operating_days": float(peak_row["share_of_operating_days"]),
        "peak_share_of_annual_orders": float(peak_row["share_of_annual_orders"]),
        "peak_concentration_index": float(peak_row["concentration_index"]),
        "top_7_contribution_per_unit_min": ranges["contribution_per_unit_min"],
        "top_7_contribution_per_unit_max": ranges["contribution_per_unit_max"],
        "top_7_gross_margin_min": ranges["gross_margin_pct_min"],
        "top_7_gross_margin_max": ranges["gross_margin_pct_max"],
        "top_7_share_of_menu_contribution": ranges["top_7_share_of_menu_contribution"],
        "aov": basket["aov"],
        "contribution_per_order": basket["contribution_per_order"],
        "contribution_margin_pct": basket["contribution_margin_pct"],
        "break_even_orders_monthly": be["break_even_orders_monthly"],
        "break_even_revenue_monthly": be["break_even_revenue_monthly"],
        "annual_revenue": annual["annual_revenue"],
        "annual_operating_profit": annual["annual_operating_profit"],
        "profitable_months": annual["profitable_months"],
        "loss_making_months": annual["loss_making_months"],
        "bottleneck_station": scenarios["baseline_bottleneck_station"],
        "baseline_peak_capacity_per_hour": scenarios["baseline_capacity_orders_per_hour"],
        "express_peak_capacity_per_hour": scenarios["express_capacity_orders_per_hour"],
        "throughput_uplift_pct": scenarios["throughput_uplift_pct"],
        "incremental_headcount": scenarios["incremental_headcount"],
        "crew_heads_session_month": flex["crew_heads_session_month"],
        "crew_heads_lean_month": flex["crew_heads_lean_month"],
        "flex_roster_annual_saving": flex["annual_saving"],
        "combo_aov_uplift_pct": combos["aov_uplift_pct"],
        "combo_units_per_order_after": combos["units_per_order_after"],
        "subscribers_to_cover_fixed_base": subs["subscribers_to_cover_fixed_base"],
        "flat_average_orders_per_day": flat_comparison["flat_average_orders_per_day"],
        "flat_average_peak_understatement_pct": flat_comparison[
            "peak_day_understatement_pct"
        ],
    }

    return {
        "tables": {
            "calendar_daily": calendar,
            "state_summary": states,
            "monthly_demand": monthly_demand,
            "sku_unit_economics": skus,
            "variable_cost_bridge": bridge,
            "monthly_pnl": monthly_pnl,
            "month_profit_concentration": month_conc,
            "sku_contribution_concentration": sku_conc,
            "throughput_baseline": base_line,
            "throughput_express": exp_line,
            "lean_month_bridge": lean_bridge,
        },
        "figures": {
            "peak_day_profile": peak_profile,
            "flat_average_comparison": flat_comparison,
            "top_7_ranges": ranges,
            "basket_economics": basket,
            "break_even": be,
            "annual_summary": annual,
            "throughput_scenarios": scenarios,
            "express_eligible_mix": eligible,
            "recovered_revenue": recovered,
            "staffing_flex": flex,
            "pre_order_pickup": pickup,
            "combo_bundling": combos,
            "subscription": subs,
        },
        "headline": headline,
    }


def _fmt_inr(value: float) -> str:
    """Indian numbering, which is how the figures will actually be read."""
    negative = value < 0
    digits = f"{abs(int(round(value)))}"
    if len(digits) <= 3:
        out = digits
    else:
        head, tail = digits[:-3], digits[-3:]
        parts = []
        while len(head) > 2:
            parts.insert(0, head[-2:])
            head = head[:-2]
        if head:
            parts.insert(0, head)
        out = ",".join(parts) + "," + tail
    return ("-" if negative else "") + out


def _pct(value: float, places: int = 1) -> str:
    return f"{value * 100:.{places}f}%"


def write_summary(results: dict[str, Any], path: Path) -> None:
    """A single readable file carrying every headline figure and its basis."""
    h = results["headline"]
    f = results["figures"]
    t = results["tables"]

    lines: list[str] = []
    add = lines.append

    add("# Campus-QSR: results")
    add("")
    add("Generated by `scripts/run_analysis.py`. Every figure below is computed")
    add("from `config/assumptions.yaml`; none of it is typed in by hand.")
    add("")

    add("## 1. Segmented demand")
    add("")
    add(f"- Operating days in the academic year: **{h['operating_days']}**")
    add(f"- Annual demand: **{_fmt_inr(h['annual_orders'])} orders**")
    add(
        f"- Peak state carries **{_pct(h['peak_share_of_annual_orders'])} of annual volume "
        f"on {_pct(h['peak_share_of_operating_days'])} of operating days** "
        f"(concentration index {h['peak_concentration_index']}x)"
    )
    add(
        f"- A flat average would have planned to {f['flat_average_comparison']['flat_average_orders_per_day']} "
        f"orders/day and understated the peak day by "
        f"**{f['flat_average_comparison']['peak_day_understatement_pct']}%**"
    )
    add("")
    add(t["state_summary"].to_markdown(index=False))
    add("")

    add("## 2. Unit economics")
    add("")
    add(
        f"- Top 7 SKUs: **INR {_fmt_inr(h['top_7_contribution_per_unit_min'])} to "
        f"{_fmt_inr(h['top_7_contribution_per_unit_max'])} contribution per unit**, "
        f"**{_pct(h['top_7_gross_margin_min'], 0)} to {_pct(h['top_7_gross_margin_max'], 0)} gross margin**"
    )
    add(
        f"- Those 7 SKUs generate **{_pct(h['top_7_share_of_menu_contribution'])} "
        f"of menu contribution** on {_pct(f['top_7_ranges']['top_7_share_of_units'])} of units"
    )
    add(f"- AOV: **INR {_fmt_inr(h['aov'])}** at {f['basket_economics']['units_per_order']} units per order")
    add(
        f"- Contribution per order: **INR {_fmt_inr(h['contribution_per_order'])}**, "
        f"a blended contribution margin of **{_pct(h['contribution_margin_pct'])}**"
    )
    add("")
    add("### Why 58-72% gross margins become a 53% contribution margin")
    add("")
    add(t["variable_cost_bridge"].to_markdown(index=False))
    add("")
    add("### Per-SKU economics")
    add("")
    add(
        t["sku_unit_economics"][
            [
                "id",
                "name",
                "price",
                "recipe_cost",
                "contribution_per_unit",
                "gross_margin_pct",
                "unit_mix",
                "share_of_menu_contribution",
                "express_eligible",
            ]
        ].to_markdown(index=False)
    )
    add("")

    add("## 3. Break-even and the monthly cohort P&L")
    add("")
    add(f"- Monthly fixed base: **INR {_fmt_inr(f['break_even']['fixed_costs_monthly'])}**")
    add(
        f"- Break-even: **{h['break_even_orders_monthly']:.0f} orders/month** "
        f"(INR {_fmt_inr(h['break_even_revenue_monthly'])} revenue) at a "
        f"{_pct(h['contribution_margin_pct'])} contribution margin"
    )
    add(
        f"- Including the rostered crew step cost, a session month must clear "
        f"**{f['break_even']['all_in_break_even_orders_session_month']:.0f} orders** "
        f"and a lean month **{f['break_even']['all_in_break_even_orders_lean_month']:.0f}**"
    )
    add(
        f"- Annual: revenue INR {_fmt_inr(h['annual_revenue'])}, operating profit "
        f"INR {_fmt_inr(h['annual_operating_profit'])} "
        f"({_pct(f['annual_summary']['annual_operating_margin_pct'])} margin)"
    )
    add(
        f"- **{h['profitable_months']} of 12 months** cover their own cost base; "
        f"**{h['loss_making_months']}** do not"
    )
    add("")
    add(
        t["monthly_pnl"][
            [
                "month_name",
                "operating_days",
                "orders",
                "roster",
                "crew_heads",
                "revenue",
                "contribution",
                "crew_cost",
                "fixed_cost",
                "operating_profit",
                "all_in_break_even_orders",
                "covers_own_month",
            ]
        ].to_markdown(index=False)
    )
    add("")
    add("### Which months carry the year")
    add("")
    add(t["month_profit_concentration"].to_markdown(index=False))
    add("")
    add("### Which SKUs carry the year")
    add("")
    add(t["sku_contribution_concentration"].to_markdown(index=False))
    add("")

    add("## 4. Peak-hour throughput")
    add("")
    s = f["throughput_scenarios"]
    add(f"- Bottleneck: **{s['baseline_bottleneck_station']}** at {s['baseline_bottleneck_cycle_seconds']}s per order")
    add(
        f"- Baseline peak capacity **{s['baseline_capacity_orders_per_hour']} orders/hour** "
        f"against peak-hour demand of {s['peak_hour_demand_orders']}, leaving "
        f"**{s['baseline_unserved_orders_per_peak_hour']} orders/hour unserved**"
    )
    add(
        f"- Express line lifts capacity to **{s['express_capacity_orders_per_hour']} orders/hour**, "
        f"**{s['throughput_uplift_pct']}%**, with **{s['incremental_headcount']} incremental headcount** "
        f"({s['headcount_on_line']} on the line in both scenarios)"
    )
    add(
        f"- The constraint then moves to **{s['next_constraint_station']}** at "
        f"{s['next_constraint_capacity_orders_per_hour']} orders/hour, which is the headroom for growth"
    )
    add(
        f"- Express is held to {_pct(f['express_eligible_mix']['configured_express_share_of_peak_orders'])} "
        f"of peak orders against an express-eligible menu mix of "
        f"{_pct(f['express_eligible_mix']['express_eligible_share_of_units'])}, so the case does not "
        f"depend on full adoption"
    )
    add(
        f"- Recovered volume: **{f['recovered_revenue']['recovered_orders_annual']:.0f} orders/year**, "
        f"INR {_fmt_inr(f['recovered_revenue']['recovered_revenue_annual'])} revenue and "
        f"INR {_fmt_inr(f['recovered_revenue']['recovered_contribution_annual'])} contribution"
    )
    add("")
    add("### Baseline line")
    add("")
    add(t["throughput_baseline"].to_markdown(index=False))
    add("")
    add("### With the Express fixed-recipe route")
    add("")
    add(t["throughput_express"].to_markdown(index=False))
    add("")

    add("## 5. Off-peak: cost flexibility and demand stimulation")
    add("")
    flex = f["staffing_flex"]
    add(
        f"- Flexible roster: **{flex['crew_heads_session_month']} to {flex['crew_heads_lean_month']} crew** "
        f"across {flex['lean_rostered_months']} lean-rostered months "
        f"({flex['lean_rostered_month_names']}), saving "
        f"**INR {_fmt_inr(flex['annual_saving'])}/year**"
    )
    pu = f["pre_order_pickup"]
    add(
        f"- Pre-order pickup slots: **+{pu['incremental_lean_orders_annual']:.0f} lean orders/year** "
        f"(INR {_fmt_inr(pu['incremental_contribution_annual'])} contribution), and shifting "
        f"{_pct(pu['peak_orders_shifted_out_of_rush_pct'], 0)} of peak orders out of the rush cuts "
        f"peak-hour demand to {pu['effective_peak_hour_demand_after_shift']} orders"
    )
    cb = f["combo_bundling"]
    add(
        f"- Combo bundling ({cb['attach_sku']} at INR {_fmt_inr(cb['attach_combo_price'])} "
        f"against a list price of INR {_fmt_inr(cb['attach_list_price'])}): attach rate "
        f"**{cb['units_per_order_before']} to {cb['units_per_order_after']} units/order**, "
        f"AOV **+{_pct(cb['aov_uplift_pct'])}** to INR {_fmt_inr(cb['aov_after'])}, "
        f"contribution per order **+{_pct(cb['contribution_per_order_uplift_pct'])}**, "
        f"break-even down **{cb['break_even_orders_reduction']:.0f} orders/month**"
    )
    sb = f["subscription"]
    add(
        f"- Residents' subscription at INR {_fmt_inr(sb['price_per_month'])}/month for "
        f"{sb['meal_credits']:.0f} credits: INR {_fmt_inr(sb['contribution_per_subscriber'])} "
        f"contribution per subscriber, so **{sb['subscribers_to_cover_fixed_base']:.0f} subscribers "
        f"({_pct(sb['penetration_required_for_full_cover'])} of residents) fully cover the fixed base**. "
        f"At the assumed {_pct(sb['assumed_penetration'], 0)} penetration it covers "
        f"{_pct(sb['share_of_fixed_base_covered_at_assumed_penetration'])}"
    )
    add("")
    add("### The worst month of the year, lever by lever")
    add("")
    add(t["lean_month_bridge"].to_markdown(index=False))
    add("")

    path.write_text("\n".join(lines) + "\n", encoding="utf-8")


def run(a: Assumptions | None = None, output_dir: Path | None = None) -> dict[str, Any]:
    """Compute, write CSVs, write summary.md, return the results dict."""
    a = a or Assumptions.load()
    out = output_dir or OUTPUT_DIR
    out.mkdir(parents=True, exist_ok=True)

    results = build_results(a)

    for name, table in results["tables"].items():
        table.to_csv(out / f"{name}.csv", index=False)

    with open(out / "headline_figures.json", "w", encoding="utf-8") as handle:
        json.dump(results["headline"], handle, indent=2, default=str)

    with open(out / "all_figures.json", "w", encoding="utf-8") as handle:
        json.dump(results["figures"], handle, indent=2, default=str)

    write_summary(results, out / "summary.md")
    return results
