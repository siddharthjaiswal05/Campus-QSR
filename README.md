# Campus-QSR

Unit economics and throughput optimization for a campus quick-service restaurant.
MBA787M course project, Prof. Suman Saurabh.

A flat daily-average forecast hides where a QSR actually makes or loses money: which
hours are the bottleneck, which SKUs carry the P&L, and where headcount is genuinely
the constraint versus where it is not. This analysis rebuilds the picture around those
questions instead of the average.

## Demand: segmented, not flat

Flat-average forecasting was replaced with a **segmented demand model** across three
calendar-driven traffic states — peak, regular, and lean.

That model sizes annual demand at **~40,100 orders**, and surfaces the constraint that
actually matters: **31% of volume concentrates in just 13% of operating days**.
Seasonality, not average daily throughput, is the real planning problem.

## Unit economics: bottom-up, by SKU

Per-SKU unit economics were built for the **top 7 products**:

- **₹93-193** contribution per unit sold
- **58-72%** gross margin

Combined with a monthly cohort-level P&L, this gives a **break-even of ~1,900
orders/month** against a **53% contribution margin**, and identifies which months and
which SKUs actually carry annual profitability, rather than assuming all of them do
equally.

## The peak-hour bottleneck

The **throughput bottleneck** was diagnosed at the customization station specifically,
not the kitchen as a whole. The proposed intervention is an **"Express" fixed-recipe
SKU line** — a deliberate trade of personalization for service velocity at peak.

Projected impact: **~30% higher peak-hour throughput at zero incremental headcount**.
The constraint was process design, not staffing.

## Off-peak: cost structure and demand

For lean periods, two levers:

- A **flexible cost structure**, cutting variable staffing from **12 to 8** in lean
  months
- An **off-peak demand-stimulation roadmap**: pre-order pickup slots, combo bundling
  to lift **attach rate** and **AOV**, and a residents' subscription to cover fixed
  costs through vacation periods
