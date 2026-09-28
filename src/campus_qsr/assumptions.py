"""Load and validate the assumption set.

Every module in this package takes its inputs from here. No analysis module
holds a literal business number of its own, so the config file is the only
place an assumption can be changed.
"""

from __future__ import annotations

import datetime as dt
from dataclasses import dataclass
from pathlib import Path
from typing import Any

import yaml

PROJECT_ROOT = Path(__file__).resolve().parents[2]
DEFAULT_CONFIG = PROJECT_ROOT / "config" / "assumptions.yaml"
OUTPUT_DIR = PROJECT_ROOT / "outputs"

WEEKDAY_NAMES = [
    "Monday",
    "Tuesday",
    "Wednesday",
    "Thursday",
    "Friday",
    "Saturday",
    "Sunday",
]


@dataclass(frozen=True)
class Window:
    """An inclusive date range carrying a human-readable label."""

    start: dt.date
    end: dt.date
    label: str

    def contains(self, day: dt.date) -> bool:
        return self.start <= day <= self.end


def _as_date(value: Any) -> dt.date:
    if isinstance(value, dt.date):
        return value
    return dt.date.fromisoformat(str(value))


def _windows(raw: list[dict[str, Any]]) -> list[Window]:
    return [
        Window(_as_date(w["start"]), _as_date(w["end"]), w.get("label", ""))
        for w in raw
    ]


class Assumptions:
    """Typed accessor over the YAML config."""

    def __init__(self, raw: dict[str, Any]):
        self.raw = raw
        self._validate()

    # -- construction ------------------------------------------------------
    @classmethod
    def load(cls, path: Path | str | None = None) -> "Assumptions":
        path = Path(path) if path else DEFAULT_CONFIG
        with open(path, "r", encoding="utf-8") as handle:
            return cls(yaml.safe_load(handle))

    # -- calendar ----------------------------------------------------------
    @property
    def year_start(self) -> dt.date:
        return _as_date(self.raw["calendar"]["year_start"])

    @property
    def year_end(self) -> dt.date:
        return _as_date(self.raw["calendar"]["year_end"])

    @property
    def peak_windows(self) -> list[Window]:
        return _windows(self.raw["calendar"]["peak_windows"])

    @property
    def lean_windows(self) -> list[Window]:
        return _windows(self.raw["calendar"]["lean_windows"])

    @property
    def maintenance_windows(self) -> list[Window]:
        return _windows(self.raw["calendar"]["closures"]["maintenance_shutdown"])

    @property
    def institute_holidays(self) -> set[dt.date]:
        return {
            _as_date(d)
            for d in self.raw["calendar"]["closures"]["institute_holidays"]
        }

    @property
    def closed_weekdays_in_lean(self) -> set[str]:
        return set(self.raw["calendar"]["closures"]["closed_weekdays_in_lean"])

    @property
    def service_hours_per_day(self) -> int:
        return int(self.raw["calendar"]["service_hours_per_day"])

    # -- demand ------------------------------------------------------------
    @property
    def base_orders(self) -> float:
        return float(self.raw["demand"]["base_orders_per_regular_weekday"])

    @property
    def state_multipliers(self) -> dict[str, float]:
        return {k: float(v) for k, v in self.raw["demand"]["state_multipliers"].items()}

    @property
    def dow_factors(self) -> dict[str, float]:
        return {k: float(v) for k, v in self.raw["demand"]["day_of_week_factors"].items()}

    @property
    def peak_hour_share(self) -> float:
        return float(self.raw["demand"]["peak_hour_share_of_day"])

    # -- menu --------------------------------------------------------------
    @property
    def top_7(self) -> list[dict[str, Any]]:
        return list(self.raw["skus"]["top_7"])

    @property
    def tail(self) -> dict[str, Any]:
        return dict(self.raw["skus"]["tail"])

    @property
    def units_per_order(self) -> float:
        return float(self.raw["basket"]["units_per_order"])

    # -- costs -------------------------------------------------------------
    @property
    def order_variable_costs(self) -> dict[str, float]:
        return {k: float(v) for k, v in self.raw["order_variable_costs"].items()}

    @property
    def fixed_costs_monthly(self) -> dict[str, float]:
        return {k: float(v) for k, v in self.raw["fixed_costs_monthly"].items()}

    @property
    def total_fixed_monthly(self) -> float:
        return sum(self.fixed_costs_monthly.values())

    @property
    def staffing(self) -> dict[str, float]:
        return {k: float(v) for k, v in self.raw["staffing"].items()}

    # -- throughput and off-peak ------------------------------------------
    @property
    def throughput(self) -> dict[str, Any]:
        return self.raw["throughput"]

    @property
    def offpeak(self) -> dict[str, Any]:
        return self.raw["offpeak"]

    # -- validation --------------------------------------------------------
    def _validate(self) -> None:
        errors: list[str] = []

        if self.year_end <= self.year_start:
            errors.append("calendar.year_end must fall after calendar.year_start")

        for name in WEEKDAY_NAMES:
            if name not in self.dow_factors:
                errors.append(f"demand.day_of_week_factors is missing {name}")

        for state in ("peak", "regular", "lean"):
            if state not in self.state_multipliers:
                errors.append(f"demand.state_multipliers is missing {state}")

        unit_mix = sum(s["unit_mix"] for s in self.top_7) + self.tail["unit_mix"]
        if abs(unit_mix - 1.0) > 1e-9:
            errors.append(f"unit mix over top_7 plus tail must sum to 1.0, got {unit_mix:.4f}")

        for sku in self.top_7:
            if sku["variable_cost"] >= sku["price"]:
                errors.append(f"{sku['id']} has variable cost at or above price")

        for window_set, label in (
            (self.peak_windows, "peak"),
            (self.lean_windows, "lean"),
        ):
            for w in window_set:
                if w.end < w.start:
                    errors.append(f"{label} window '{w.label}' ends before it starts")

        overlaps = [
            (p.label, l.label)
            for p in self.peak_windows
            for l in self.lean_windows
            if p.start <= l.end and l.start <= p.end
        ]
        if overlaps:
            errors.append(f"peak and lean windows overlap: {overlaps}")

        if errors:
            raise ValueError("Invalid assumptions:\n  - " + "\n  - ".join(errors))
