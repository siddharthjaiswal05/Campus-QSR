#!/usr/bin/env python3
"""Run the full Campus-QSR analysis and write outputs/.

    python3 scripts/run_analysis.py
    python3 scripts/run_analysis.py --config config/assumptions.yaml
"""

from __future__ import annotations

import argparse
import sys
from pathlib import Path

sys.path.insert(0, str(Path(__file__).resolve().parents[1] / "src"))

from campus_qsr.assumptions import OUTPUT_DIR, Assumptions  # noqa: E402
from campus_qsr.report import run  # noqa: E402


def main() -> int:
    parser = argparse.ArgumentParser(description="Run the Campus-QSR analysis.")
    parser.add_argument("--config", type=Path, default=None,
                        help="Path to an assumptions YAML file.")
    parser.add_argument("--output-dir", type=Path, default=None,
                        help="Where to write tables and the summary.")
    parser.add_argument("--no-charts", action="store_true",
                        help="Skip chart rendering.")
    args = parser.parse_args()

    a = Assumptions.load(args.config)
    out = args.output_dir or OUTPUT_DIR
    results = run(a, out)

    if not args.no_charts:
        try:
            from campus_qsr.charts import render_all
            render_all(results, out / "charts")
        except ImportError as exc:
            print(f"Charts skipped ({exc}).")

    h = results["headline"]
    print(f"Annual orders                  {h['annual_orders']:,}")
    print(f"Operating days                  {h['operating_days']}")
    print(f"Peak share of volume / of days  {h['peak_share_of_annual_orders']:.1%}"
          f" on {h['peak_share_of_operating_days']:.1%}")
    print(f"Contribution margin             {h['contribution_margin_pct']:.1%}")
    print(f"Break-even orders per month     {h['break_even_orders_monthly']:,.0f}")
    print(f"Peak throughput uplift          {h['throughput_uplift_pct']}%"
          f" at {h['incremental_headcount']} incremental heads")
    print(f"\nWrote {out}/")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
