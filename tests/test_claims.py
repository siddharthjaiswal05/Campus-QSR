"""Every headline claim, asserted against the computed model.

The point of this file is that no number in the README is typed in by hand. If
an assumption changes and a claim stops holding, this fails. Runs under pytest
or standalone:

    python3 tests/test_claims.py
    pytest tests/test_claims.py
"""

from __future__ import annotations

import sys
from pathlib import Path

sys.path.insert(0, str(Path(__file__).resolve().parents[1] / "src"))

from campus_qsr.assumptions import Assumptions  # noqa: E402
from campus_qsr.report import build_results  # noqa: E402

A = Assumptions.load()
R = build_results(A)
H = R["headline"]
F = R["figures"]
T = R["tables"]


# --- Claim 1: segmented demand ------------------------------------------------

def test_annual_demand_is_about_40100_orders():
    assert 39_500 <= H["annual_orders"] <= 40_700, H["annual_orders"]


def test_peak_concentration_is_31_percent_of_volume_in_13_percent_of_days():
    assert round(H["peak_share_of_annual_orders"] * 100) == 31
    assert round(H["peak_share_of_operating_days"] * 100) == 13


def test_three_traffic_states_are_all_populated():
    states = T["state_summary"]
    assert set(states["state"]) == {"peak", "regular", "lean"}
    assert (states["operating_days"] > 0).all()


def test_peak_day_carries_more_than_twice_its_share_of_the_calendar():
    assert H["peak_concentration_index"] > 2.0


def test_flat_average_materially_understates_the_peak_day():
    # The reason the segmented model exists at all.
    assert H["flat_average_peak_understatement_pct"] > 100


def test_seasonality_dominates_day_of_week():
    m = A.state_multipliers
    d = A.dow_factors
    state_spread = m["peak"] / m["lean"]
    dow_spread = max(d.values()) / min(d.values())
    # Traffic state swings demand ~3.9x; day of week swings it ~1.4x. Planning to
    # the weekly rhythm instead of the academic calendar is the larger error.
    assert state_spread > dow_spread * 2


# --- Claim 2: per-SKU unit economics and break-even ---------------------------

def test_top_7_contribution_per_unit_spans_93_to_193():
    assert H["top_7_contribution_per_unit_min"] == 93
    assert H["top_7_contribution_per_unit_max"] == 193


def test_top_7_gross_margins_span_58_to_72_percent():
    assert 0.58 <= H["top_7_gross_margin_min"] < 0.59
    assert 0.71 <= H["top_7_gross_margin_max"] <= 0.72


def test_exactly_seven_headline_skus():
    assert len(A.top_7) == 7
    assert int(T["sku_unit_economics"]["in_top_7"].sum()) == 7


def test_blended_contribution_margin_is_53_percent():
    assert round(H["contribution_margin_pct"] * 100) == 53


def test_break_even_is_about_1900_orders_per_month():
    assert 1_850 <= H["break_even_orders_monthly"] <= 1_950


def test_contribution_margin_sits_below_every_sku_gross_margin():
    # The bridge from gross margin to contribution margin must go downward,
    # otherwise the order-level cost lines are not being applied.
    skus = T["sku_unit_economics"]
    top = skus[skus["in_top_7"]]
    assert H["contribution_margin_pct"] < top["gross_margin_pct"].min()


def test_variable_cost_bridge_reconciles_to_contribution_per_order():
    final = T["variable_cost_bridge"].iloc[-1]["running_contribution"]
    assert abs(final - H["contribution_per_order"]) < 0.02


def test_monthly_pnl_has_twelve_cohorts():
    assert len(T["monthly_pnl"]) == 12


def test_pnl_reconciles_to_the_calendar_demand_model():
    assert int(T["monthly_pnl"]["orders"].sum()) == H["annual_orders"]


def test_profitability_is_concentrated_not_uniform():
    # The claim is that specific months carry the year, so a uniform spread
    # would falsify it.
    assert H["profitable_months"] < 12
    assert H["loss_making_months"] > 0


def test_top_7_carry_the_menu():
    assert H["top_7_share_of_menu_contribution"] > 0.85


def test_sku_contribution_concentration_curve_closes_at_one():
    assert abs(T["sku_contribution_concentration"]["cumulative_share"].iloc[-1] - 1.0) < 0.01


# --- Claim 3: the peak-hour bottleneck and the Express line -------------------

def test_bottleneck_is_the_customization_station():
    assert H["bottleneck_station"] == "Customization station"


def test_bottleneck_is_a_single_station_not_the_whole_kitchen():
    base = T["throughput_baseline"]
    assert int(base["is_bottleneck"].sum()) == 1
    non_bottleneck = base[~base["is_bottleneck"]]["utilisation_at_line_capacity"]
    # Every other station has real slack, so labour minutes are not the problem.
    assert (non_bottleneck < 0.8).all()


def test_express_line_lifts_peak_throughput_about_30_percent():
    assert 28.0 <= H["throughput_uplift_pct"] <= 32.0


def test_express_line_adds_zero_headcount():
    assert H["incremental_headcount"] == 0
    assert int(T["throughput_baseline"]["servers"].sum()) == int(
        T["throughput_express"]["servers"].sum()
    )


def test_baseline_cannot_serve_peak_demand_but_express_can():
    s = F["throughput_scenarios"]
    assert s["baseline_unserved_orders_per_peak_hour"] > 0
    assert s["express_unserved_orders_per_peak_hour"] == 0


def test_express_share_is_covered_by_the_eligible_menu():
    # The intervention must not assume more express volume than the fixed-recipe
    # SKUs can actually supply.
    e = F["express_eligible_mix"]
    assert e["configured_express_share_of_peak_orders"] <= e["express_eligible_share_of_units"]
    assert e["express_eligible_skus"] >= 3


def test_constraint_moves_rather_than_disappears():
    s = F["throughput_scenarios"]
    assert s["next_constraint_capacity_orders_per_hour"] > s["express_capacity_orders_per_hour"]


# --- Claim 4: flexible cost structure and off-peak demand --------------------

def test_roster_flexes_from_12_to_8_in_lean_months():
    assert H["crew_heads_session_month"] == 12
    assert H["crew_heads_lean_month"] == 8


def test_flex_roster_is_actually_exercised_and_saves_money():
    flex = F["staffing_flex"]
    assert flex["lean_rostered_months"] >= 1
    assert flex["annual_saving"] > 0


def test_lean_months_are_rostered_lean_and_session_months_are_not():
    pnl = T["monthly_pnl"]
    for _, row in pnl.iterrows():
        expected = "lean" if row["lean_day_share"] >= A.staffing["lean_month_threshold"] else "session"
        assert row["roster"] == expected, row["month_name"]


def test_combo_bundling_lifts_attach_rate_and_aov():
    cb = F["combo_bundling"]
    assert cb["units_per_order_after"] > cb["units_per_order_before"]
    assert cb["aov_after"] > cb["aov_before"]


def test_combo_bundling_is_contribution_accretive():
    # A bundle that lifts AOV while destroying contribution is not a lever.
    cb = F["combo_bundling"]
    assert cb["blended_contribution_per_order_after"] > cb["contribution_per_order_before"]
    assert cb["break_even_orders_after"] < cb["break_even_orders_before"]


def test_pre_order_pickup_adds_lean_volume_and_relieves_the_rush():
    pu = F["pre_order_pickup"]
    assert pu["incremental_lean_orders_annual"] > 0
    assert pu["effective_peak_hour_demand_after_shift"] < F["throughput_scenarios"][
        "peak_hour_demand_orders"
    ]


def test_subscription_is_sized_to_cover_the_fixed_base():
    sb = F["subscription"]
    assert sb["contribution_per_subscriber"] > 0
    assert (
        abs(
            sb["subscribers_to_cover_fixed_base"] * sb["contribution_per_subscriber"]
            - sb["fixed_base_monthly"]
        )
        < sb["contribution_per_subscriber"] * 1.5
    )


def test_subscription_penetration_required_is_plausible():
    # If covering the fixed base needed most of the campus, the lever would be
    # a fantasy rather than a recommendation.
    assert F["subscription"]["penetration_required_for_full_cover"] < 0.20


def test_levers_turn_the_worst_month_around():
    bridge = T["lean_month_bridge"]
    assert bridge.iloc[0]["running_operating_profit"] < 0
    assert bridge.iloc[-1]["running_operating_profit"] > 0


# --- Integrity ---------------------------------------------------------------

def test_assumptions_validate_and_mix_sums_to_one():
    total = sum(s["unit_mix"] for s in A.top_7) + A.tail["unit_mix"]
    assert abs(total - 1.0) < 1e-9


def test_no_operating_day_is_also_a_closed_day():
    cal = T["calendar_daily"]
    assert (cal[cal["is_open"]]["closed_for"] == "").all()
    assert (cal[~cal["is_open"]]["orders"] == 0).all()


def test_every_output_table_is_non_empty():
    for name, table in T.items():
        assert len(table) > 0, name


def _main() -> int:
    tests = [(n, o) for n, o in sorted(globals().items())
             if n.startswith("test_") and callable(o)]
    failed = []
    for name, fn in tests:
        try:
            fn()
            print(f"  pass  {name}")
        except AssertionError as exc:
            failed.append((name, exc))
            print(f"  FAIL  {name}: {exc}")
    print(f"\n{len(tests) - len(failed)}/{len(tests)} claims verified")
    return 1 if failed else 0


if __name__ == "__main__":
    raise SystemExit(_main())
