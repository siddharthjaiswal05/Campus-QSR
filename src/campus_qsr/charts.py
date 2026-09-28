"""Chart rendering for the analysis.

Six figures, each answering one question the analysis turns on. Rendered in a
light and a dark variant from the same validated palette, because a dark step is
chosen for the dark surface rather than flipped into it.

Palette slots and the diverging pair were checked with a colourblind-separation
validator before being used. The aqua slot sits below 3:1 against the light
surface, so the lean series always carries a direct label, and every figure has
a CSV of the same data beside it in outputs/.
"""

from __future__ import annotations

from pathlib import Path
from typing import Any

import matplotlib

matplotlib.use("Agg")
import matplotlib.pyplot as plt  # noqa: E402
from matplotlib.lines import Line2D  # noqa: E402
from matplotlib.patches import Patch  # noqa: E402

# Categorical slots 1, 2, 3 and the diverging poles, per the validated palette.
LIGHT = {
    "surface": "#fcfcfb",
    "text": "#0b0b0b",
    "text_secondary": "#52514e",
    "muted": "#8a8983",
    "grid": "#e6e5e1",
    "peak": "#2a78d6",
    "regular": "#eb6834",
    "lean": "#1baf7a",
    "positive": "#2a78d6",
    "negative": "#e34948",
    "neutral": "#c9c8c3",
}

DARK = {
    "surface": "#1a1a19",
    "text": "#ffffff",
    "text_secondary": "#c3c2b7",
    "muted": "#8f8e86",
    "grid": "#383835",
    "peak": "#3987e5",
    "regular": "#d95926",
    "lean": "#199e70",
    "positive": "#3987e5",
    "negative": "#e66767",
    "neutral": "#4a4a46",
}

STATE_LABELS = {"peak": "Peak", "regular": "Regular", "lean": "Lean"}


def _style(fig, axes, c: dict[str, str]) -> None:
    """Recessive axes and grid, so the marks carry the chart."""
    fig.patch.set_facecolor(c["surface"])
    for ax in axes if isinstance(axes, (list, tuple)) else [axes]:
        ax.set_facecolor(c["surface"])
        for side in ("top", "right"):
            ax.spines[side].set_visible(False)
        for side in ("left", "bottom"):
            ax.spines[side].set_color(c["grid"])
            ax.spines[side].set_linewidth(1.0)
        ax.tick_params(colors=c["text_secondary"], labelsize=9, length=0)
        ax.title.set_color(c["text"])
        ax.xaxis.label.set_color(c["text_secondary"])
        ax.yaxis.label.set_color(c["text_secondary"])


def _title(ax, title: str, subtitle: str, c: dict[str, str]) -> None:
    ax.set_title(title, fontsize=13, fontweight="600", loc="left", pad=18,
                 color=c["text"])
    ax.text(0, 1.015, subtitle, transform=ax.transAxes, fontsize=9.5,
            color=c["text_secondary"], va="bottom")


def _save(fig, path: Path) -> None:
    path.parent.mkdir(parents=True, exist_ok=True)
    fig.savefig(path, dpi=150, bbox_inches="tight",
                facecolor=fig.get_facecolor())
    plt.close(fig)


def _inr(value: float) -> str:
    """Lakh notation, which is how these numbers get discussed."""
    return f"{value / 100000:.2f}L"


# --- 1. Seasonality signature -------------------------------------------------

def chart_seasonality(results: dict[str, Any], c: dict[str, str], path: Path) -> None:
    cal = results["tables"]["calendar_daily"]
    trading = cal[cal["is_open"]].copy()

    fig, ax = plt.subplots(figsize=(11, 4.2))
    for state in ("regular", "peak", "lean"):
        rows = trading[trading["state"] == state]
        ax.bar(rows["date"], rows["orders"], width=1.0,
               color=c[state], linewidth=0, label=STATE_LABELS[state])

    flat = results["figures"]["flat_average_comparison"]["flat_average_orders_per_day"]
    ax.axhline(flat, color=c["muted"], linewidth=2, linestyle=(0, (4, 3)), zorder=3)
    # Anchored to the quiet right-hand tail, clear of both the peaks and the legend.
    ax.text(trading["date"].iloc[-2], flat + 10,
            f"Flat average, {flat:.0f} orders/day", fontsize=9,
            color=c["text_secondary"], va="bottom", ha="right")

    h = results["headline"]
    _title(
        ax,
        "One year of daily demand, by traffic state",
        f"{h['peak_share_of_annual_orders']:.0%} of volume lands on "
        f"{h['peak_share_of_operating_days']:.0%} of operating days. The flat "
        f"average describes almost no real day.",
        c,
    )
    ax.set_ylabel("Orders per day")
    ax.set_ylim(0, trading["orders"].max() * 1.22)
    ax.grid(axis="y", color=c["grid"], linewidth=1, alpha=0.9)
    ax.set_axisbelow(True)
    ax.margins(x=0.01)
    # Upper left is the one region no peak reaches.
    legend = ax.legend(frameon=False, loc="upper left", ncol=3, fontsize=9)
    for text in legend.get_texts():
        text.set_color(c["text_secondary"])
    _style(fig, ax, c)
    _save(fig, path)


# --- 2. Concentration curve ---------------------------------------------------

def chart_concentration(results: dict[str, Any], c: dict[str, str], path: Path) -> None:
    cal = results["tables"]["calendar_daily"]
    trading = cal[cal["is_open"]].sort_values("orders", ascending=False)

    n = len(trading)
    cum_days = [(i + 1) / n for i in range(n)]
    total = trading["orders"].sum()
    cum_orders, running = [], 0
    for value in trading["orders"]:
        running += value
        cum_orders.append(running / total)

    fig, ax = plt.subplots(figsize=(6.4, 5.4))
    ax.plot([0, 1], [0, 1], color=c["muted"], linewidth=2,
            linestyle=(0, (4, 3)), label="If demand were flat")
    ax.plot(cum_days, cum_orders, color=c["peak"], linewidth=2.5,
            label="Actual demand")

    h = results["headline"]
    x = h["peak_share_of_operating_days"]
    y = h["peak_share_of_annual_orders"]
    ax.plot([x], [y], marker="o", markersize=9, color=c["peak"],
            markeredgecolor=c["surface"], markeredgewidth=2, zorder=5)
    ax.annotate(
        f"Peak days\n{x:.0%} of days, {y:.0%} of volume",
        xy=(x, y), xytext=(x + 0.12, y - 0.19), fontsize=9.5,
        color=c["text"],
        arrowprops=dict(arrowstyle="-", color=c["muted"], linewidth=1.2),
    )
    ax.vlines(x, 0, y, color=c["grid"], linewidth=1.5, zorder=1)
    ax.hlines(y, 0, x, color=c["grid"], linewidth=1.5, zorder=1)

    _title(ax, "Demand concentration",
           "Operating days ranked busiest first. The gap from the diagonal is "
           "the planning problem.", c)
    ax.set_xlabel("Cumulative share of operating days")
    ax.set_ylabel("Cumulative share of annual orders")
    ax.set_xlim(0, 1)
    ax.set_ylim(0, 1)
    ax.set_xticks([0, 0.25, 0.5, 0.75, 1.0])
    ax.set_yticks([0, 0.25, 0.5, 0.75, 1.0])
    ax.set_xticklabels(["0", "25%", "50%", "75%", "100%"])
    ax.set_yticklabels(["0", "25%", "50%", "75%", "100%"])
    ax.grid(color=c["grid"], linewidth=1, alpha=0.9)
    ax.set_axisbelow(True)
    legend = ax.legend(frameon=False, loc="lower right", fontsize=9)
    for text in legend.get_texts():
        text.set_color(c["text_secondary"])
    _style(fig, ax, c)
    _save(fig, path)


# --- 3. Per-SKU unit economics ------------------------------------------------

def chart_sku_economics(results: dict[str, Any], c: dict[str, str], path: Path) -> None:
    df = results["tables"]["sku_unit_economics"]
    top = df[df["in_top_7"]].sort_values("contribution_per_unit")

    fig, ax = plt.subplots(figsize=(8.6, 4.8))
    ypos = range(len(top))
    ax.barh(list(ypos), top["contribution_per_unit"], height=0.62,
            color=c["peak"], linewidth=0)

    for i, (_, row) in enumerate(top.iterrows()):
        ax.text(row["contribution_per_unit"] + 3, i,
                f"INR {row['contribution_per_unit']:.0f}   "
                f"{row['gross_margin_pct']:.0%} GM",
                va="center", fontsize=9, color=c["text"])

    cm = results["headline"]["contribution_margin_pct"]
    _title(ax, "Contribution per unit, top 7 SKUs",
           f"Gross margin runs "
           f"{results['headline']['top_7_gross_margin_min']:.0%} to "
           f"{results['headline']['top_7_gross_margin_max']:.0%} at the plate. "
           f"Order-level costs pull the blended contribution margin to {cm:.0%}.",
           c)
    ax.set_yticks(list(ypos))
    ax.set_yticklabels(top["name"], fontsize=9.5, color=c["text"])
    ax.set_xlabel("Contribution per unit (INR)")
    ax.set_xlim(0, top["contribution_per_unit"].max() * 1.36)
    ax.grid(axis="x", color=c["grid"], linewidth=1, alpha=0.9)
    ax.set_axisbelow(True)
    _style(fig, ax, c)
    _save(fig, path)


# --- 4. Monthly P&L -----------------------------------------------------------

def chart_monthly_pnl(results: dict[str, Any], c: dict[str, str], path: Path) -> None:
    pnl = results["tables"]["monthly_pnl"]
    labels = [m.replace(" 20", " '") for m in pnl["month_name"]]
    profit = pnl["operating_profit"].tolist()
    colors = [c["positive"] if p > 0 else c["negative"] for p in profit]

    fig, ax = plt.subplots(figsize=(10.4, 4.6))
    ax.bar(labels, profit, width=0.66, color=colors, linewidth=0)
    ax.axhline(0, color=c["text_secondary"], linewidth=1.2)

    low = min(profit) * 1.62
    high = max(profit) * 1.42
    crew_band = low * 0.90          # a reserved strip below every value label
    for i, (p, roster) in enumerate(zip(profit, pnl["roster"])):
        offset = 12000 if p > 0 else -12000
        ax.text(i, p + offset, _inr(p), ha="center",
                va="bottom" if p > 0 else "top", fontsize=8.5, color=c["text"])
        if roster == "lean":
            ax.text(i, crew_band, "8 crew", ha="center", fontsize=8,
                    color=c["lean"], fontweight="600", va="center")

    h = results["headline"]
    _title(ax, "Operating profit by month",
           f"{h['profitable_months']} of 12 months cover their own cost base. "
           f"Months marked 8 crew are rostered lean; the rest carry 12.", c)
    ax.set_ylabel("Operating profit (INR)")
    ax.set_yticks(ax.get_yticks())
    ax.set_yticklabels([_inr(v) for v in ax.get_yticks()])
    ax.set_ylim(low, high)
    ax.grid(axis="y", color=c["grid"], linewidth=1, alpha=0.9)
    ax.set_axisbelow(True)
    legend = ax.legend(
        handles=[Patch(facecolor=c["positive"], label="Covers its cost base"),
                 Patch(facecolor=c["negative"], label="Does not")],
        frameon=False, loc="upper left", ncol=2, fontsize=9,
        bbox_to_anchor=(0, 1.0))
    for text in legend.get_texts():
        text.set_color(c["text_secondary"])
    _style(fig, ax, c)
    _save(fig, path)


# --- 5. Peak-hour bottleneck --------------------------------------------------

def chart_bottleneck(results: dict[str, Any], c: dict[str, str], path: Path) -> None:
    base = results["tables"]["throughput_baseline"]
    exp = results["tables"]["throughput_express"]
    s = results["figures"]["throughput_scenarios"]

    order = base.sort_values("effective_cycle_seconds")
    names = order["station"].tolist()
    base_v = order["effective_cycle_seconds"].tolist()
    exp_v = [
        float(exp[exp["station"] == n]["effective_cycle_seconds"].iloc[0])
        for n in names
    ]

    fig, ax = plt.subplots(figsize=(9.2, 4.8))
    h = 0.34
    ypos = list(range(len(names)))
    ax.barh([y + h / 2 + 0.015 for y in ypos], base_v, height=h,
            color=c["peak"], linewidth=0, label="Today")
    ax.barh([y - h / 2 - 0.015 for y in ypos], exp_v, height=h,
            color=c["regular"], linewidth=0, label="With the Express route")

    limit = s["baseline_bottleneck_cycle_seconds"]
    ax.axvline(limit, color=c["muted"], linewidth=2, linestyle=(0, (4, 3)), zorder=3)
    # Sits in the reserved strip above the tallest bar, not across it.
    ax.text(limit + 2.5, len(names) - 0.34,
            f"Line capacity today: {limit:.0f}s, "
            f"{s['baseline_capacity_orders_per_hour']:.0f} orders/hour",
            ha="left", fontsize=9, color=c["text_secondary"], va="center")

    idx = names.index(s["baseline_bottleneck_station"])
    # Placed past the capacity line so it never crosses the dashed rule.
    ax.text(limit + 2.5, idx - h / 2 - 0.015,
            f"{exp_v[idx]:.1f}s, "
            f"{s['express_capacity_orders_per_hour']:.0f} orders/hour",
            va="center", fontsize=9, color=c["text"], fontweight="600")

    _title(ax, "Peak-hour cycle time by station",
           f"One station sets the line. Re-routing "
           f"{results['figures']['express_eligible_mix']['configured_express_share_of_peak_orders']:.0%} "
           f"of peak orders past it lifts throughput "
           f"{s['throughput_uplift_pct']:.0f}% with {s['incremental_headcount']} "
           f"added heads.", c)
    ax.set_yticks(ypos)
    ax.set_yticklabels(names, fontsize=9.5, color=c["text"])
    ax.set_xlabel("Effective seconds per order (station time / servers)")
    ax.set_xlim(0, max(base_v) * 1.62)
    ax.set_ylim(-0.6, len(names) - 0.15)
    ax.grid(axis="x", color=c["grid"], linewidth=1, alpha=0.9)
    ax.set_axisbelow(True)
    legend = ax.legend(frameon=False, loc="lower right", fontsize=9)
    for text in legend.get_texts():
        text.set_color(c["text_secondary"])
    _style(fig, ax, c)
    _save(fig, path)


# --- 6. Lean month waterfall --------------------------------------------------

def chart_lean_bridge(results: dict[str, Any], c: dict[str, str], path: Path) -> None:
    bridge = results["tables"]["lean_month_bridge"]
    steps = bridge["step"].tolist()
    deltas = bridge["delta"].tolist()
    running = bridge["running_operating_profit"].tolist()

    fig, ax = plt.subplots(figsize=(9.6, 5.0))
    short = {
        "Flexible roster (12 to 8 crew)": "Flexible\nroster",
        "Pre-order pickup slots": "Pre-order\npickup",
        "Combo bundling on existing orders": "Combo\nbundling",
        "Residents' subscription": "Residents'\nsubscription",
    }
    labels = ["Flat roster\nbaseline"] + [
        short.get(step, step.replace(" ", "\n")) for step in steps[1:]
    ] + ["Position\nafter levers"]

    ax.bar(0, running[0], width=0.6, color=c["negative"], linewidth=0)
    for i in range(1, len(steps)):
        bottom = running[i - 1] if deltas[i] > 0 else running[i]
        ax.bar(i, abs(deltas[i]), bottom=bottom, width=0.6,
               color=c["positive"] if deltas[i] > 0 else c["negative"],
               linewidth=0)
        ax.plot([i - 1 + 0.3, i - 0.3], [running[i - 1]] * 2,
                color=c["muted"], linewidth=1.2, linestyle=(0, (2, 2)))

    final = len(steps)
    ax.bar(final, running[-1], width=0.6,
           color=c["positive"] if running[-1] > 0 else c["negative"], linewidth=0)
    ax.plot([final - 1 + 0.3, final - 0.3], [running[-1]] * 2,
            color=c["muted"], linewidth=1.2, linestyle=(0, (2, 2)))

    ax.text(0, running[0] - 14000, _inr(running[0]), ha="center", va="top",
            fontsize=9, color=c["text"], fontweight="600")
    for i in range(1, len(steps)):
        top = max(running[i - 1], running[i])
        ax.text(i, top + 8000, f"+{_inr(deltas[i])}", ha="center", va="bottom",
                fontsize=9, color=c["text"])
    ax.text(final, running[-1] + 14000, _inr(running[-1]), ha="center",
            va="bottom", fontsize=9, color=c["text"], fontweight="600")

    ax.axhline(0, color=c["text_secondary"], linewidth=1.2)
    _title(ax, f"{bridge['month'].iloc[0]}, the worst month of the year",
           "Every lever applied to the month that decides whether the outlet can "
           "trade through a vacation unaided.", c)
    ax.set_xticks(range(len(labels)))
    ax.set_xticklabels(labels, fontsize=9, color=c["text"])
    ax.set_ylim(min(running) * 1.45, max(running) * 2.6)
    ax.set_ylabel("Operating profit (INR)")
    ax.set_yticks(ax.get_yticks())
    ax.set_yticklabels([_inr(v) for v in ax.get_yticks()])
    ax.grid(axis="y", color=c["grid"], linewidth=1, alpha=0.9)
    ax.set_axisbelow(True)
    legend = ax.legend(
        handles=[Patch(facecolor=c["positive"], label="Improves the month"),
                 Patch(facecolor=c["negative"], label="Loss position")],
        frameon=False, loc="upper left", ncol=2, fontsize=9)
    for text in legend.get_texts():
        text.set_color(c["text_secondary"])
    _style(fig, ax, c)
    _save(fig, path)


CHARTS = {
    "01_seasonality": chart_seasonality,
    "02_demand_concentration": chart_concentration,
    "03_sku_unit_economics": chart_sku_economics,
    "04_monthly_pnl": chart_monthly_pnl,
    "05_peak_hour_bottleneck": chart_bottleneck,
    "06_lean_month_bridge": chart_lean_bridge,
}


def render_all(results: dict[str, Any], out_dir: Path) -> list[Path]:
    """Render every figure in both themes. Returns the paths written."""
    written: list[Path] = []
    for theme_name, colors in (("light", LIGHT), ("dark", DARK)):
        target = out_dir if theme_name == "light" else out_dir / "dark"
        for name, fn in CHARTS.items():
            path = target / f"{name}.png"
            fn(results, colors, path)
            written.append(path)
    return written
