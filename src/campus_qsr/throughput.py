"""Peak-hour throughput: station cycle times, bottleneck, and the Express line.

The line is modelled as serial stations, each with a fixed number of parallel
servers. Effective cycle time per order at a station is

    seconds_per_order / servers

and peak-hour capacity is set by the single slowest station, not by the sum of
the work. This is the distinction the analysis turns on: the kitchen in
aggregate has enough labour minutes to clear the peak, but one station does not.

The Express scenario re-routes work across the existing stations. Headcount is
identical in both scenarios, and the model asserts that.
"""

from __future__ import annotations

import pandas as pd

from .assumptions import Assumptions


def _stations(a: Assumptions) -> list[dict]:
    return [dict(s) for s in a.throughput["stations"]]


def baseline_line(a: Assumptions) -> pd.DataFrame:
    """Per-station effective cycle time and capacity as the line runs today."""
    rows = []
    for s in _stations(a):
        effective = s["seconds_per_order"] / s["servers"]
        rows.append(
            {
                "station": s["name"],
                "servers": s["servers"],
                "seconds_per_order": float(s["seconds_per_order"]),
                "effective_cycle_seconds": round(effective, 2),
                "station_capacity_orders_per_hour": round(3600 / effective, 1),
            }
        )
    df = pd.DataFrame(rows)
    bottleneck = df["effective_cycle_seconds"].max()
    df["is_bottleneck"] = df["effective_cycle_seconds"] == bottleneck
    df["utilisation_at_line_capacity"] = (
        df["effective_cycle_seconds"] / bottleneck
    ).round(3)
    return df


def express_line(a: Assumptions) -> pd.DataFrame:
    """Per-station effective cycle time with the Express route in place.

    An express order skips the customization dialogue but still needs a lid,
    garnish and drizzle, draws its base from a pre-batched hold cabinet, and
    carries a small routing penalty at finish and pack.
    """
    cfg = a.throughput["express"]
    e = float(cfg["share_of_peak_orders"])
    cust_name = a.throughput["customization_station_name"]
    finish_name = a.throughput["finish_station_name"]
    base_name = "Base prep (griddle/fryer)"

    rows = []
    for s in _stations(a):
        seconds = float(s["seconds_per_order"])

        if s["name"] == cust_name:
            # Blend of the untouched custom path and the near-zero express path.
            seconds = (1 - e) * seconds + e * float(cfg["customization_seconds"])
            note = f"{e:.0%} of orders bypass the customization dialogue"
        elif s["name"] == base_name:
            seconds = (1 - e) * seconds + e * float(cfg["base_prep_seconds"])
            note = "Express draws a pre-batched base from the hold cabinet"
        elif s["name"] == finish_name:
            seconds = seconds + e * float(cfg["finish_penalty_seconds"])
            note = "Absorbs express assembly and the routing tax"
        else:
            note = "Unchanged"

        effective = seconds / s["servers"]
        rows.append(
            {
                "station": s["name"],
                "servers": s["servers"],
                "seconds_per_order": round(seconds, 2),
                "effective_cycle_seconds": round(effective, 2),
                "station_capacity_orders_per_hour": round(3600 / effective, 1),
                "note": note,
            }
        )

    df = pd.DataFrame(rows)
    bottleneck = df["effective_cycle_seconds"].max()
    df["is_bottleneck"] = df["effective_cycle_seconds"] == bottleneck
    df["utilisation_at_line_capacity"] = (
        df["effective_cycle_seconds"] / bottleneck
    ).round(3)
    return df


def _capacity(df: pd.DataFrame) -> tuple[str, float, float]:
    row = df.loc[df["effective_cycle_seconds"].idxmax()]
    cycle = float(row["effective_cycle_seconds"])
    return str(row["station"]), cycle, 3600 / cycle


def express_eligible_mix(a: Assumptions) -> dict[str, float]:
    """Cross-check the express share against the menu, not against ambition.

    The express route is only credible for SKUs that can be produced to a fixed
    recipe. This reports the share of units those SKUs represent, so the
    configured peak share can be judged against it.
    """
    eligible = [s for s in a.top_7 if s["express_eligible"]]
    eligible_mix = sum(s["unit_mix"] for s in eligible)
    return {
        "express_eligible_skus": len(eligible),
        "express_eligible_sku_names": ", ".join(s["name"] for s in eligible),
        "express_eligible_share_of_units": round(eligible_mix, 4),
        "configured_express_share_of_peak_orders": float(
            a.throughput["express"]["share_of_peak_orders"]
        ),
    }


def throughput_scenarios(a: Assumptions, peak_profile: dict) -> dict[str, float]:
    """Baseline against Express, sized to observed peak-hour demand."""
    base = baseline_line(a)
    exp = express_line(a)

    base_station, base_cycle, base_cap = _capacity(base)
    exp_station, exp_cycle, exp_cap = _capacity(exp)

    demand = peak_profile["peak_hour_orders_mean_peak_day"]
    demand_busiest = peak_profile["peak_hour_orders_busiest_day"]

    # Second constraint after the intervention, which is where growth stops next.
    exp_sorted = exp.sort_values("effective_cycle_seconds", ascending=False)
    next_station = str(exp_sorted.iloc[1]["station"])
    next_cap = round(3600 / float(exp_sorted.iloc[1]["effective_cycle_seconds"]), 1)

    base_heads = int(base["servers"].sum())
    exp_heads = int(exp["servers"].sum())
    assert base_heads == exp_heads, "Express scenario must not add headcount"

    return {
        "baseline_bottleneck_station": base_station,
        "baseline_bottleneck_cycle_seconds": round(base_cycle, 2),
        "baseline_capacity_orders_per_hour": round(base_cap, 1),
        "express_bottleneck_station": exp_station,
        "express_bottleneck_cycle_seconds": round(exp_cycle, 2),
        "express_capacity_orders_per_hour": round(exp_cap, 1),
        "throughput_uplift_pct": round((exp_cap / base_cap - 1) * 100, 1),
        "incremental_headcount": exp_heads - base_heads,
        "headcount_on_line": exp_heads,
        "peak_hour_demand_orders": demand,
        "peak_hour_demand_busiest_day": demand_busiest,
        "baseline_unserved_orders_per_peak_hour": round(max(0.0, demand - base_cap), 1),
        "express_unserved_orders_per_peak_hour": round(max(0.0, demand - exp_cap), 1),
        "baseline_demand_coverage": round(base_cap / demand, 3),
        "express_demand_coverage": round(exp_cap / demand, 3),
        "next_constraint_station": next_station,
        "next_constraint_capacity_orders_per_hour": next_cap,
    }


def recovered_revenue(a: Assumptions, calendar, scenarios: dict, basket: dict) -> dict:
    """Value the orders the baseline line turns away at peak.

    Unserved peak-hour demand is a real loss only on days where the rush
    actually exceeds capacity, so this counts peak-state operating days only.
    """
    from .calendar_model import operating_days

    trading = operating_days(calendar)
    peak_days = int((trading["state"] == "peak").sum())

    recovered_per_peak_day = min(
        scenarios["baseline_unserved_orders_per_peak_hour"],
        scenarios["express_capacity_orders_per_hour"]
        - scenarios["baseline_capacity_orders_per_hour"],
    )
    annual_orders = recovered_per_peak_day * peak_days

    return {
        "peak_state_operating_days": peak_days,
        "recovered_orders_per_peak_day": round(recovered_per_peak_day, 1),
        "recovered_orders_annual": round(annual_orders, 0),
        "recovered_revenue_annual": round(annual_orders * basket["aov"], 0),
        "recovered_contribution_annual": round(
            annual_orders * basket["contribution_per_order"], 0
        ),
    }
