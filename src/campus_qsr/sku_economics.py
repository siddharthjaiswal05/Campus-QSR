"""Bottom-up per-SKU unit economics.

Two layers are kept deliberately separate, because collapsing them is what
produces the wrong answer:

  1. SKU gross margin: price less recipe cost at the plate. This is the number
     that says which menu items are worth protecting at peak.
  2. Order contribution margin: revenue less recipe cost less the order-level
     variable costs no single SKU owns (packaging, wastage, MDR, aggregator
     commission), across the full basket including the thin tail menu.

Layer 2 sits materially below every individual gross margin in layer 1. The
break-even has to be struck on layer 2, and the menu decisions on layer 1.
"""

from __future__ import annotations

import pandas as pd

from .assumptions import Assumptions


def sku_table(a: Assumptions) -> pd.DataFrame:
    """Per-unit economics for the top 7 SKUs, plus the tail bucket for context."""
    rows = []
    for sku in a.top_7:
        contribution = sku["price"] - sku["variable_cost"]
        rows.append(
            {
                "id": sku["id"],
                "name": sku["name"],
                "in_top_7": True,
                "price": float(sku["price"]),
                "recipe_cost": float(sku["variable_cost"]),
                "contribution_per_unit": float(contribution),
                "gross_margin_pct": round(contribution / sku["price"], 4),
                "unit_mix": float(sku["unit_mix"]),
                "express_eligible": bool(sku["express_eligible"]),
                "customization_seconds": float(sku["customization_seconds"]),
            }
        )

    tail = a.tail
    tail_contribution = tail["price"] - tail["variable_cost"]
    rows.append(
        {
            "id": "TAIL",
            "name": tail["name"],
            "in_top_7": False,
            "price": float(tail["price"]),
            "recipe_cost": float(tail["variable_cost"]),
            "contribution_per_unit": float(tail_contribution),
            "gross_margin_pct": round(tail_contribution / tail["price"], 4),
            "unit_mix": float(tail["unit_mix"]),
            "express_eligible": False,
            "customization_seconds": float(tail["customization_seconds"]),
        }
    )

    df = pd.DataFrame(rows)
    # Share of total menu contribution each SKU generates per unit of mix. This
    # is what ranks the menu by P&L weight rather than by popularity.
    df["contribution_weight"] = df["unit_mix"] * df["contribution_per_unit"]
    df["share_of_menu_contribution"] = (
        df["contribution_weight"] / df["contribution_weight"].sum()
    ).round(4)
    df["revenue_weight"] = df["unit_mix"] * df["price"]
    df["share_of_menu_revenue"] = (
        df["revenue_weight"] / df["revenue_weight"].sum()
    ).round(4)
    return df


def top_7_ranges(a: Assumptions) -> dict[str, float]:
    """The headline unit-economics spread across the top 7."""
    df = sku_table(a)
    top = df[df["in_top_7"]]
    return {
        "contribution_per_unit_min": float(top["contribution_per_unit"].min()),
        "contribution_per_unit_max": float(top["contribution_per_unit"].max()),
        "gross_margin_pct_min": round(float(top["gross_margin_pct"].min()), 4),
        "gross_margin_pct_max": round(float(top["gross_margin_pct"].max()), 4),
        "top_7_share_of_units": round(float(top["unit_mix"].sum()), 4),
        "top_7_share_of_menu_contribution": round(
            float(top["share_of_menu_contribution"].sum()), 4
        ),
        "top_7_share_of_menu_revenue": round(
            float(top["share_of_menu_revenue"].sum()), 4
        ),
    }


def basket_economics(a: Assumptions) -> dict[str, float]:
    """Mix-weighted per-unit and per-order economics, down to contribution margin."""
    df = sku_table(a)

    revenue_per_unit = float((df["unit_mix"] * df["price"]).sum())
    recipe_cost_per_unit = float((df["unit_mix"] * df["recipe_cost"]).sum())
    gross_contribution_per_unit = revenue_per_unit - recipe_cost_per_unit

    units = a.units_per_order
    aov = revenue_per_unit * units
    recipe_cost_per_order = recipe_cost_per_unit * units
    gross_contribution_per_order = gross_contribution_per_unit * units

    c = a.order_variable_costs
    packaging = c["packaging_per_order"]
    consumables = c["consumables_per_order"]
    wastage = aov * c["wastage_pct_of_revenue"]
    mdr = aov * c["payment_mdr_pct_of_revenue"]
    aggregator = (
        aov * c["aggregator_commission_pct"] * c["aggregator_share_of_orders"]
    )
    other_variable = packaging + consumables + wastage + mdr + aggregator

    contribution_per_order = gross_contribution_per_order - other_variable

    return {
        "revenue_per_unit": round(revenue_per_unit, 2),
        "recipe_cost_per_unit": round(recipe_cost_per_unit, 2),
        "gross_contribution_per_unit": round(gross_contribution_per_unit, 2),
        "blended_gross_margin_pct": round(
            gross_contribution_per_unit / revenue_per_unit, 4
        ),
        "units_per_order": units,
        "aov": round(aov, 2),
        "recipe_cost_per_order": round(recipe_cost_per_order, 2),
        "gross_contribution_per_order": round(gross_contribution_per_order, 2),
        "packaging_per_order": round(packaging, 2),
        "consumables_per_order": round(consumables, 2),
        "wastage_per_order": round(wastage, 2),
        "payment_mdr_per_order": round(mdr, 2),
        "aggregator_commission_per_order": round(aggregator, 2),
        "other_variable_per_order": round(other_variable, 2),
        "contribution_per_order": round(contribution_per_order, 2),
        "contribution_margin_pct": round(contribution_per_order / aov, 4),
    }


def variable_cost_bridge(a: Assumptions) -> pd.DataFrame:
    """Walk from AOV down to contribution per order, line by line.

    Reading this table top to bottom is the answer to why a menu of 58 to 72
    percent gross margins delivers a contribution margin in the low fifties.
    """
    b = basket_economics(a)
    aov = b["aov"]
    steps = [
        ("Average order value", aov, "revenue"),
        ("Recipe cost at the plate", -b["recipe_cost_per_order"], "cost"),
        ("Packaging", -b["packaging_per_order"], "cost"),
        ("Consumables", -b["consumables_per_order"], "cost"),
        ("Wastage and spoilage", -b["wastage_per_order"], "cost"),
        ("Payment processing (MDR)", -b["payment_mdr_per_order"], "cost"),
        ("Aggregator commission", -b["aggregator_commission_per_order"], "cost"),
    ]
    rows, running = [], 0.0
    for label, amount, kind in steps:
        running += amount
        rows.append(
            {
                "line": label,
                "kind": kind,
                "per_order": round(amount, 2),
                "pct_of_aov": round(amount / aov, 4),
                "running_contribution": round(running, 2),
                "running_margin_pct": round(running / aov, 4),
            }
        )
    return pd.DataFrame(rows)
