"""Monthly cohort-level P&L and break-even.

Cost behaviour is split three ways rather than two, because the middle category
is where the flexible cost structure lives:

  variable   moves with every order (recipe, packaging, wastage, MDR, commission)
  step       fixed within a month, reset between months (crew roster)
  fixed      unchanged across the year (licence fee, core payroll, depreciation)

The headline break-even is struck against the fixed base at the blended
contribution margin. A second, stricter break-even is reported per month
including that month's rostered crew, because that is the number that decides
whether a given month pays for itself.
"""

from __future__ import annotations

import pandas as pd

from .assumptions import Assumptions
from .sku_economics import basket_economics, sku_table


def break_even(a: Assumptions) -> dict[str, float]:
    """Break-even against the monthly fixed base."""
    b = basket_economics(a)
    fixed = a.total_fixed_monthly
    cpo = b["contribution_per_order"]

    s = a.staffing
    crew_session = s["crew_heads_session_month"] * s["crew_cost_per_head_monthly"]
    crew_lean = s["crew_heads_lean_month"] * s["crew_cost_per_head_monthly"]

    return {
        "fixed_costs_monthly": fixed,
        "contribution_per_order": cpo,
        "contribution_margin_pct": b["contribution_margin_pct"],
        "aov": b["aov"],
        "break_even_orders_monthly": round(fixed / cpo, 1),
        "break_even_revenue_monthly": round(fixed / b["contribution_margin_pct"], 2),
        "break_even_orders_daily_at_26_days": round(fixed / cpo / 26, 1),
        "crew_cost_session_month": crew_session,
        "crew_cost_lean_month": crew_lean,
        "all_in_break_even_orders_session_month": round((fixed + crew_session) / cpo, 1),
        "all_in_break_even_orders_lean_month": round((fixed + crew_lean) / cpo, 1),
    }


def monthly_pnl(a: Assumptions, monthly_demand: pd.DataFrame) -> pd.DataFrame:
    """Cohort P&L, one row per operating month."""
    b = basket_economics(a)
    s = a.staffing
    fixed = a.total_fixed_monthly
    cpo = b["contribution_per_order"]

    df = monthly_demand.copy()
    df["roster"] = df["lean_day_share"].apply(
        lambda share: "lean" if share >= s["lean_month_threshold"] else "session"
    )
    df["crew_heads"] = df["roster"].map(
        {
            "lean": int(s["crew_heads_lean_month"]),
            "session": int(s["crew_heads_session_month"]),
        }
    )

    df["revenue"] = (df["orders"] * b["aov"]).round(0)
    df["recipe_cost"] = (df["orders"] * b["recipe_cost_per_order"]).round(0)
    df["other_variable_cost"] = (df["orders"] * b["other_variable_per_order"]).round(0)
    df["contribution"] = (df["orders"] * cpo).round(0)
    df["contribution_margin_pct"] = (df["contribution"] / df["revenue"]).round(4)

    df["crew_cost"] = df["crew_heads"] * s["crew_cost_per_head_monthly"]
    df["fixed_cost"] = fixed
    df["operating_profit"] = (
        df["contribution"] - df["crew_cost"] - df["fixed_cost"]
    ).round(0)
    df["operating_margin_pct"] = (df["operating_profit"] / df["revenue"]).round(4)

    df["all_in_break_even_orders"] = (
        (df["fixed_cost"] + df["crew_cost"]) / cpo
    ).round(0)
    df["orders_vs_break_even"] = df["orders"] - df["all_in_break_even_orders"]
    df["covers_own_month"] = df["operating_profit"] > 0

    # What a flat 12-head roster would have cost, to price the flex lever.
    flat_crew = s["crew_heads_session_month"] * s["crew_cost_per_head_monthly"]
    df["crew_saving_vs_flat_roster"] = flat_crew - df["crew_cost"]

    cols = [
        "month",
        "month_name",
        "operating_days",
        "orders",
        "lean_day_share",
        "roster",
        "crew_heads",
        "revenue",
        "recipe_cost",
        "other_variable_cost",
        "contribution",
        "contribution_margin_pct",
        "crew_cost",
        "fixed_cost",
        "operating_profit",
        "operating_margin_pct",
        "all_in_break_even_orders",
        "orders_vs_break_even",
        "covers_own_month",
        "crew_saving_vs_flat_roster",
    ]
    return df[cols]


def annual_summary(pnl: pd.DataFrame) -> dict[str, float]:
    """Roll the twelve cohorts into the annual position."""
    revenue = float(pnl["revenue"].sum())
    contribution = float(pnl["contribution"].sum())
    profit = float(pnl["operating_profit"].sum())

    return {
        "annual_orders": int(pnl["orders"].sum()),
        "annual_revenue": revenue,
        "annual_contribution": contribution,
        "annual_contribution_margin_pct": round(contribution / revenue, 4),
        "annual_crew_cost": float(pnl["crew_cost"].sum()),
        "annual_fixed_cost": float(pnl["fixed_cost"].sum()),
        "annual_operating_profit": profit,
        "annual_operating_margin_pct": round(profit / revenue, 4),
        "profitable_months": int(pnl["covers_own_month"].sum()),
        "loss_making_months": int((~pnl["covers_own_month"]).sum()),
        "annual_crew_saving_vs_flat_roster": float(
            pnl["crew_saving_vs_flat_roster"].sum()
        ),
    }


def month_contribution_concentration(pnl: pd.DataFrame) -> pd.DataFrame:
    """Which months actually carry annual profitability, ranked."""
    df = pnl[["month_name", "orders", "contribution", "operating_profit"]].copy()
    df = df.sort_values("operating_profit", ascending=False).reset_index(drop=True)

    positive = df[df["operating_profit"] > 0]["operating_profit"].sum()
    df["share_of_positive_profit"] = (
        df["operating_profit"].where(df["operating_profit"] > 0, 0) / positive
    ).round(4)
    df["cumulative_share"] = df["share_of_positive_profit"].cumsum().round(4)
    df["rank"] = df.index + 1
    return df


def sku_contribution_concentration(a: Assumptions, annual_orders: int) -> pd.DataFrame:
    """Annual units and contribution by SKU, ranked, with a cumulative curve."""
    units_total = annual_orders * a.units_per_order
    df = sku_table(a).copy()

    df["annual_units"] = (df["unit_mix"] * units_total).round(0)
    df["annual_revenue"] = (df["annual_units"] * df["price"]).round(0)
    df["annual_gross_contribution"] = (
        df["annual_units"] * df["contribution_per_unit"]
    ).round(0)

    df = df.sort_values("annual_gross_contribution", ascending=False).reset_index(
        drop=True
    )
    total = df["annual_gross_contribution"].sum()
    df["share_of_gross_contribution"] = (
        df["annual_gross_contribution"] / total
    ).round(4)
    df["cumulative_share"] = df["share_of_gross_contribution"].cumsum().round(4)
    df["rank"] = df.index + 1

    return df[
        [
            "rank",
            "id",
            "name",
            "in_top_7",
            "price",
            "contribution_per_unit",
            "gross_margin_pct",
            "annual_units",
            "annual_revenue",
            "annual_gross_contribution",
            "share_of_gross_contribution",
            "cumulative_share",
        ]
    ]
