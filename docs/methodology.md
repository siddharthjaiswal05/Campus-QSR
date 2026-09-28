# Methodology

How each number is built, and what it depends on. Every input lives in
`config/assumptions.yaml`; nothing below is hard-coded in the analysis modules.

## 1. Why not a flat average

A single outlet serving a residential campus does not face stationary demand.
The population it serves physically leaves twice a year and concentrates on
campus during exam and fest weeks. A flat daily average sits between two states
that barely overlap: it plans to 118 orders a day against real days that run
from 68 to 318.

Three consequences follow, and each is a separate decision:

| Question | Wrong answer from a flat average | What the segmented model says |
|---|---|---|
| How much line capacity? | Size to 118/day | Size to the peak hour of a 283-order day |
| How many crew? | A constant roster | 12 in session, 8 in vacation |
| Is the outlet viable? | Yes, on average | Only if 6 months carry the other 6 |

## 2. Demand model

Each date in the academic year (1 July 2025 to 30 June 2026) is classified by
rule, not by fitted seasonality:

```
state(date)  = peak   if date falls in an exam, fest or placement window
               lean   if date falls in a vacation window
               regular otherwise

orders(date) = base * state_multiplier[state] * day_of_week_factor[weekday]
```

Closed days (institute holidays, the vacation Sunday closure, the May
maintenance shutdown) are removed before anything is computed, so every rate is
per operating day rather than per calendar day.

`base` is the one calibrated parameter: it is set so annual volume matches the
observed counter, and every other figure moves with it. The multipliers encode
the judgement that a peak day runs 2.8x a regular day and a vacation day 0.72x.

**What this model does not do.** It has no intra-day arrival distribution, no
weather term, no competitive response, and no year-over-year growth. Peak-hour
load is taken as a fixed share of the day rather than simulated, which is
adequate for sizing a bottleneck but not for queue-length prediction. A
discrete-event simulation would be the next step if wait times, rather than
capacity, became the question.

## 3. Two margin layers, kept separate

Collapsing these is the most common error in menu analysis, because it makes
every SKU look like it earns its gross margin.

**Layer 1, SKU gross margin.** Price less recipe cost at the plate. It answers
which items are worth protecting when capacity is scarce. Runs 58 to 71 percent
across the top 7.

**Layer 2, order contribution margin.** Revenue less recipe cost less the
order-level costs no single SKU owns: packaging, consumables, wastage, payment
processing, and aggregator commission on the delivered share. It also carries
the tail menu, which is thinner than any headline SKU. Lands at 53.2 percent.

The bridge in `outputs/variable_cost_bridge.csv` walks one to the other. The
break-even is struck on layer 2; menu and capacity decisions are made on
layer 1. Using layer 1 for break-even would understate the required volume by
roughly a fifth.

## 4. Three cost behaviours, not two

| Behaviour | Contents | Moves with |
|---|---|---|
| Variable | Recipe, packaging, wastage, MDR, commission | Every order |
| Step | Crew roster | Reset monthly against traffic state |
| Fixed | Licence fee, core payroll, depreciation, utilities base | Nothing, inside the year |

The headline break-even of 1,904 orders per month is struck against the fixed
base alone, which is the conventional definition and the one that is comparable
across outlets. Because crew is a real cash cost, the monthly P&L also reports
an all-in break-even including that month's roster: 3,227 orders in a session
month and 2,786 in a lean one. That second number is what decides whether a
given month pays for itself, and it is why six months do not.

## 5. Throughput

The line is modelled as serial stations with parallel servers:

```
effective_cycle(station) = seconds_per_order / servers
line_capacity            = 3600 / max(effective_cycle)
```

Capacity is set by the slowest single station, not by total labour minutes. The
kitchen has ample aggregate capacity: at the line's limit, every station other
than customization runs below 56 percent utilisation. Adding a head anywhere
except the bottleneck changes nothing, which is the argument against the
intuitive response of hiring for the rush.

The Express scenario reroutes rather than adds. Fixed-recipe SKUs bypass the
customization dialogue but still take 6 seconds there for lid and garnish, draw
a pre-batched base from a hold cabinet, and add 20 seconds at finish and pack.
Headcount is identical, and `throughput_scenarios` asserts that rather than
assuming it.

Express is sized at 25 percent of peak orders against an express-eligible menu
mix of 39 percent, so the case does not depend on full adoption of every
eligible item.

**What this model does not do.** It is deterministic. Real cycle times vary, and
variability at a bottleneck costs throughput that a mean-based model does not
see, so 64.9 orders per hour is an upper bound rather than a forecast. Nothing
here models the customer's willingness to accept a fixed recipe, which is the
genuine commercial risk in the intervention.

## 6. Off-peak levers

Each is sized on its own terms rather than assumed.

**Flexible roster.** A month is rostered lean when at least half its operating
days are lean-state. Three months qualify, releasing 4 crew each at INR 14,000,
for INR 168,000 a year.

**Pre-order pickup.** Modelled as a 4 percent lift on lean volume, and
separately as an 8 percent shift of peak orders out of the rush hour. The second
effect is the more valuable one: it buys peak capacity with no capital.

**Combo bundling.** Modelled as a priced attach, not a basket-wide discount. The
first version of this model applied a discount across the whole basket and came
out contribution-negative, because the incremental unit carries only average mix
margin while the discount applies to everything. Pricing one 70 percent gross
margin beverage down to INR 99 instead lifts contribution per order 6.9 percent.
The mechanic, not the headline, is what decides whether bundling works.

**Subscription.** Sized against the fixed base it exists to cover. At INR 1,499
for 20 credits and 68 percent redemption, each subscriber contributes INR 584,
so 415 subscribers (11.9 percent of residents) cover the fixed base outright.

**What this model does not do.** The uplift percentages for pickup and bundling
are assumptions, not measurements, and they are the softest numbers in the
analysis. The subscription treats redemption as independent of season, when a
subscriber present through a vacation would plausibly redeem more. The
break-even penetration is the robust output here; the assumed 8 percent take-up
is not.

## 7. Verification

`tests/test_claims.py` asserts all 37 headline claims against the computed
model, including the structural ones that could silently break: that the
contribution margin stays below every SKU gross margin, that the Express
scenario adds no headcount, that the P&L reconciles to the calendar, and that
bundling remains contribution-accretive. Changing an assumption that breaks a
claim fails the suite rather than quietly changing the README.
