"""Segmented, calendar-driven demand model.

The point of this module is to refuse the flat daily average. Every date in the
academic year is classified into a traffic state by an academic-calendar rule,
closed days are removed, and demand is built per operating day as

    orders = base * state_multiplier * day_of_week_factor

The concentration statistic that falls out of this (what share of annual volume
sits in what share of operating days) is the number that drives every staffing
and throughput decision downstream.
"""

from __future__ import annotations

import datetime as dt

import pandas as pd

from .assumptions import Assumptions, WEEKDAY_NAMES

STATES = ("peak", "regular", "lean")


def _classify(day: dt.date, a: Assumptions) -> tuple[str, str]:
    """Return the traffic state for a date and the window label that set it."""
    for window in a.peak_windows:
        if window.contains(day):
            return "peak", window.label
    for window in a.lean_windows:
        if window.contains(day):
            return "lean", window.label
    return "regular", "Session, regular week"


def _closure_reason(day: dt.date, state: str, a: Assumptions) -> str | None:
    if day in a.institute_holidays:
        return "Institute holiday"
    for window in a.maintenance_windows:
        if window.contains(day):
            return window.label
    weekday = WEEKDAY_NAMES[day.weekday()]
    if state == "lean" and weekday in a.closed_weekdays_in_lean:
        return f"Vacation {weekday} closure"
    return None


def build_calendar(a: Assumptions) -> pd.DataFrame:
    """One row per calendar date in the academic year, open or closed."""
    rows = []
    day = a.year_start
    while day <= a.year_end:
        state, label = _classify(day, a)
        closed_for = _closure_reason(day, state, a)
        weekday = WEEKDAY_NAMES[day.weekday()]
        is_open = closed_for is None

        if is_open:
            orders = (
                a.base_orders
                * a.state_multipliers[state]
                * a.dow_factors[weekday]
            )
            orders = int(round(orders))
        else:
            orders = 0

        rows.append(
            {
                "date": day,
                "month": day.strftime("%Y-%m"),
                "month_name": day.strftime("%b %Y"),
                "weekday": weekday,
                "state": state,
                "window": label,
                "is_open": is_open,
                "closed_for": closed_for or "",
                "orders": orders,
            }
        )
        day += dt.timedelta(days=1)

    return pd.DataFrame(rows)


def operating_days(calendar: pd.DataFrame) -> pd.DataFrame:
    """Only the days the outlet actually trades."""
    return calendar[calendar["is_open"]].reset_index(drop=True)


def state_summary(calendar: pd.DataFrame) -> pd.DataFrame:
    """Day count, volume and concentration by traffic state."""
    trading = operating_days(calendar)
    total_days = len(trading)
    total_orders = int(trading["orders"].sum())

    summary = (
        trading.groupby("state")
        .agg(operating_days=("orders", "size"), annual_orders=("orders", "sum"))
        .reindex(list(STATES))
        .fillna(0)
        .astype(int)
        .reset_index()
    )
    summary["orders_per_operating_day"] = (
        summary["annual_orders"] / summary["operating_days"]
    ).round(1)
    summary["share_of_operating_days"] = (
        summary["operating_days"] / total_days
    ).round(4)
    summary["share_of_annual_orders"] = (
        summary["annual_orders"] / total_orders
    ).round(4)
    # How much more volume a state's day carries than its share of the calendar.
    summary["concentration_index"] = (
        summary["share_of_annual_orders"] / summary["share_of_operating_days"]
    ).round(2)
    return summary


def monthly_demand(calendar: pd.DataFrame) -> pd.DataFrame:
    """Orders and state composition by month, the unit the P&L is struck on."""
    trading = operating_days(calendar)
    grouped = trading.groupby(["month", "month_name"], sort=True)

    out = grouped.agg(
        operating_days=("orders", "size"),
        orders=("orders", "sum"),
    ).reset_index()

    for state in STATES:
        counts = (
            trading[trading["state"] == state]
            .groupby("month")["orders"]
            .size()
            .rename(f"{state}_days")
        )
        out = out.merge(counts, on="month", how="left")
        out[f"{state}_days"] = out[f"{state}_days"].fillna(0).astype(int)

    out["lean_day_share"] = (out["lean_days"] / out["operating_days"]).round(3)
    out["orders_per_operating_day"] = (
        out["orders"] / out["operating_days"]
    ).round(1)
    return out.sort_values("month").reset_index(drop=True)


def peak_day_profile(a: Assumptions, calendar: pd.DataFrame) -> dict[str, float]:
    """The busiest-day and busiest-hour figures the throughput model sizes to."""
    trading = operating_days(calendar)
    peak_days = trading[trading["state"] == "peak"]
    busiest_day_orders = int(trading["orders"].max())
    mean_peak_day = float(peak_days["orders"].mean())

    return {
        "mean_peak_day_orders": round(mean_peak_day, 1),
        "busiest_day_orders": busiest_day_orders,
        "peak_hour_orders_mean_peak_day": round(mean_peak_day * a.peak_hour_share, 1),
        "peak_hour_orders_busiest_day": round(busiest_day_orders * a.peak_hour_share, 1),
        "mean_regular_day_orders": round(
            float(trading[trading["state"] == "regular"]["orders"].mean()), 1
        ),
        "mean_lean_day_orders": round(
            float(trading[trading["state"] == "lean"]["orders"].mean()), 1
        ),
    }


def flat_average_comparison(calendar: pd.DataFrame) -> dict[str, float]:
    """What a flat-average forecast would have concluded, and its error.

    This is the counterfactual the project exists to displace: sizing the line
    on mean daily throughput understates peak-day load by the gap reported here.
    """
    trading = operating_days(calendar)
    flat = float(trading["orders"].mean())
    peak_mean = float(trading[trading["state"] == "peak"]["orders"].mean())
    lean_mean = float(trading[trading["state"] == "lean"]["orders"].mean())

    return {
        "flat_average_orders_per_day": round(flat, 1),
        "peak_day_understatement_pct": round((peak_mean / flat - 1) * 100, 1),
        "lean_day_overstatement_pct": round((1 - lean_mean / flat) * 100, 1),
    }
