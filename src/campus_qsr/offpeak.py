"""Off-peak levers: flexible cost structure and demand stimulation.

Peak and off-peak are different problems and get different treatment. At peak
the constraint is capacity, so the lever is process design. Off-peak the
constraint is demand against a fixed cost base, so the levers are cost
flexibility and three demand instruments, each sized here on its own terms.
"""

from __future__ import annotations

import pandas as pd

from .assumptions import Assumptions
from .sku_economics import basket_economics, sku_table


def staffing_flex(a: Assumptions, pnl: pd.DataFrame) -> dict[str, float]:
    """What the variable roster is worth against a flat session-level roster."""
    s = a.staffing
    lean_months = pnl[pnl["roster"] == "lean"]
    per_head = s["crew_cost_per_head_monthly"]
    heads_cut = s["crew_heads_session_month"] - s["crew_heads_lean_month"]

    return {
        "crew_heads_session_month": int(s["crew_heads_session_month"]),
        "crew_heads_lean_month": int(s["crew_heads_lean_month"]),
        "heads_released_per_lean_month": int(heads_cut),
        "cost_per_head_monthly": per_head,
        "lean_rostered_months": int(len(lean_months)),
        "lean_rostered_month_names": ", ".join(lean_months["month_name"].tolist()),
        "saving_per_lean_month": heads_cut * per_head,
        "annual_saving": float(pnl["crew_saving_vs_flat_roster"].sum()),
        "annual_saving_as_pct_of_fixed_base": round(
            float(pnl["crew_saving_vs_flat_roster"].sum()) / (a.total_fixed_monthly * 12),
            4,
        ),
    }


def pre_order_pickup(a: Assumptions, pnl: pd.DataFrame, scenarios: dict) -> dict:
    """Pre-booked pickup slots: a demand lever off-peak, a queue lever at peak."""
    cfg = a.offpeak["pre_order_pickup"]
    b = basket_economics(a)
    lean_orders = float(pnl[pnl["roster"] == "lean"]["orders"].sum())

    uplift = float(cfg["lean_order_uplift_pct"])
    incremental = lean_orders * uplift
    shifted = float(cfg["peak_orders_shifted_out_of_rush_pct"])

    return {
        "lean_month_orders_base": round(lean_orders, 0),
        "lean_order_uplift_pct": uplift,
        "incremental_lean_orders_annual": round(incremental, 0),
        "incremental_contribution_annual": round(
            incremental * b["contribution_per_order"], 0
        ),
        "peak_orders_shifted_out_of_rush_pct": shifted,
        "effective_peak_hour_demand_after_shift": round(
            scenarios["peak_hour_demand_orders"] * (1 - shifted), 1
        ),
        "note": (
            "Off-peak the slot book converts intent that currently lapses. "
            "At peak the same book moves orders out of the rush hour, which "
            "buys capacity without touching the line."
        ),
    }


def combo_bundling(a: Assumptions) -> dict:
    """Bundling as a priced attach mechanic, not a basket-wide discount.

    The combo prices one high-margin item down to pull it into the basket. That
    ordering matters: discounting the whole basket would cost more than the
    incremental unit returns, because the marginal unit carries only average
    mix margin. Attaching a 70 percent gross margin beverage at a cut price
    still clears its own variable cost with room to spare.
    """
    cfg = a.offpeak["combo_bundling"]
    base = basket_economics(a)
    df = sku_table(a)
    c = a.order_variable_costs

    attach_id = str(cfg["attach_sku_id"])
    match = df[df["id"] == attach_id]
    if match.empty:
        raise ValueError(f"combo_bundling.attach_sku_id '{attach_id}' is not in the menu")
    attach = match.iloc[0]

    list_price = float(attach["price"])
    combo_price = float(cfg["attach_unit_price"])
    recipe = float(attach["recipe_cost"])
    share = float(cfg["share_of_orders_bundled"])

    # Transaction costs scale with the incremental revenue, not with the order.
    # Packaging and consumables do not: the attach item rides the same bag.
    transaction_cost = combo_price * (
        c["wastage_pct_of_revenue"]
        + c["payment_mdr_pct_of_revenue"]
        + c["aggregator_commission_pct"] * c["aggregator_share_of_orders"]
    )
    attach_contribution = combo_price - recipe - transaction_cost

    aov_after = base["aov"] + share * combo_price
    cpo_after = base["contribution_per_order"] + share * attach_contribution
    units_after = a.units_per_order + share

    return {
        "attach_sku": str(attach["name"]),
        "attach_list_price": list_price,
        "attach_combo_price": combo_price,
        "attach_discount_pct": round(1 - combo_price / list_price, 4),
        "attach_recipe_cost": recipe,
        "attach_transaction_cost": round(transaction_cost, 2),
        "attach_contribution_per_bundle": round(attach_contribution, 2),
        "attach_contribution_margin_pct": round(attach_contribution / combo_price, 4),
        "share_of_orders_bundled": share,
        "units_per_order_before": a.units_per_order,
        "units_per_order_after": round(units_after, 3),
        "attach_rate_uplift_pct": round(units_after / a.units_per_order - 1, 4),
        "aov_before": base["aov"],
        "aov_after": round(aov_after, 2),
        "aov_uplift_pct": round(aov_after / base["aov"] - 1, 4),
        "contribution_per_order_before": base["contribution_per_order"],
        "blended_contribution_per_order_after": round(cpo_after, 2),
        "contribution_per_order_uplift_pct": round(
            cpo_after / base["contribution_per_order"] - 1, 4
        ),
        "contribution_margin_pct_before": base["contribution_margin_pct"],
        "contribution_margin_pct_after": round(cpo_after / aov_after, 4),
        "break_even_orders_before": round(
            a.total_fixed_monthly / base["contribution_per_order"], 1
        ),
        "break_even_orders_after": round(a.total_fixed_monthly / cpo_after, 1),
        "break_even_orders_reduction": round(
            a.total_fixed_monthly / base["contribution_per_order"]
            - a.total_fixed_monthly / cpo_after,
            1,
        ),
    }


def subscription(a: Assumptions) -> dict:
    """Residents' subscription sized against the fixed base it has to cover.

    The instrument is deliberately fixed-cost-facing: cash arrives at the start
    of the month regardless of footfall, which is exactly what a vacation month
    lacks.
    """
    cfg = a.offpeak["subscription"]
    df = sku_table(a)
    c = a.order_variable_costs

    recipe_per_unit = float((df["unit_mix"] * df["recipe_cost"]).sum())
    units_per_meal = float(cfg["units_per_redeemed_meal"])

    price = float(cfg["price_per_month"])
    credits = float(cfg["meal_credits"])
    redemption = float(cfg["redemption_rate"])
    redeemed = credits * redemption

    cost_per_meal = (
        recipe_per_unit * units_per_meal
        + c["packaging_per_order"]
        + c["consumables_per_order"]
    )
    variable_cost = redeemed * cost_per_meal
    contribution = price - variable_cost

    fixed = a.total_fixed_monthly
    subs_for_full_cover = fixed / contribution

    population = float(cfg["resident_population"])
    penetration = float(cfg["assumed_penetration"])
    assumed_subs = population * penetration
    assumed_contribution = assumed_subs * contribution

    return {
        "price_per_month": price,
        "meal_credits": credits,
        "redemption_rate": redemption,
        "meals_redeemed_per_subscriber": round(redeemed, 2),
        "effective_price_per_redeemed_meal": round(price / redeemed, 2),
        "variable_cost_per_redeemed_meal": round(cost_per_meal, 2),
        "variable_cost_per_subscriber": round(variable_cost, 2),
        "contribution_per_subscriber": round(contribution, 2),
        "contribution_margin_pct": round(contribution / price, 4),
        "fixed_base_monthly": fixed,
        "subscribers_to_cover_fixed_base": round(subs_for_full_cover, 0),
        "penetration_required_for_full_cover": round(
            subs_for_full_cover / population, 4
        ),
        "resident_population": population,
        "assumed_penetration": penetration,
        "assumed_subscribers": round(assumed_subs, 0),
        "assumed_monthly_contribution": round(assumed_contribution, 0),
        "share_of_fixed_base_covered_at_assumed_penetration": round(
            assumed_contribution / fixed, 4
        ),
    }


def lean_month_bridge(a: Assumptions, pnl: pd.DataFrame, subs: dict, pickup: dict,
                      combos: dict) -> pd.DataFrame:
    """Walk the worst month of the year from a flat roster to all levers applied.

    The worst month is the one that decides whether the outlet can trade through
    a vacation without a cash injection, so it is the right month to stress.
    Step one is the counterfactual: what that month loses on a flat session
    roster, before any lever is pulled.
    """
    worst = pnl.loc[pnl["operating_profit"].idxmin()]
    base_orders = float(worst["orders"])
    b = basket_economics(a)

    lean_months = max(1, int((pnl["roster"] == "lean").sum()))
    pickup_orders = pickup["incremental_lean_orders_annual"] / lean_months
    flex_saving = float(worst["crew_saving_vs_flat_roster"])

    steps = [
        ("Operating profit on a flat 12-head roster",
         float(worst["operating_profit"]) - flex_saving),
        ("Flexible roster (12 to 8 crew)", flex_saving),
        ("Pre-order pickup slots", pickup_orders * b["contribution_per_order"]),
        ("Combo bundling on existing orders",
         base_orders
         * (combos["blended_contribution_per_order_after"]
            - combos["contribution_per_order_before"])),
        ("Residents' subscription", subs["assumed_monthly_contribution"]),
    ]

    rows, running = [], 0.0
    for i, (label, delta) in enumerate(steps):
        running = delta if i == 0 else running + delta
        rows.append(
            {
                "month": worst["month_name"],
                "step": label,
                "delta": round(delta, 0),
                "running_operating_profit": round(running, 0),
            }
        )
    return pd.DataFrame(rows)
