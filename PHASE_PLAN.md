# X10 Engine Implementation Plan

## Priority
X10 Engine remains the primary decision-support layer.

## Phase 1 — Scanner foundation
- Preserve X10Engine as the decision engine.
- Improve candidate discovery beyond the current arbitrary first-200 instrument slice.
- Use fast quote filtering before expensive historical technical analysis.
- Keep Angel One as primary market-data source and Yahoo/yfinance only as fallback.
- Preserve memory-conscious batching/concurrency.
- Separate X10 score from confidence/probability presentation.
- Preserve entry zone, stop-loss, targets, trailing stop, risk/reward and don't-chase outputs.

## Phase 2 — Index intelligence
- NIFTY 50, BANK NIFTY, SENSEX, INDIA VIX and additional important indices where supported.
- Current price, dynamic support, resistance, target zones and bullish/neutral/bearish bias.
- Click index cards to open detailed analysis.

## Phase 3 — Opportunity ranking
- Early momentum/acceleration detection.
- Avoid rewarding already-exploded price moves.
- Affordable-stock preference with liquidity, quality and risk filters.
- Rank opportunities using X10 score, setup quality, momentum acceleration and risk/reward.

## Phase 4 — UI decision-support layout
- Market status first.
- X10 opportunities prominently above generic scanner utilities.
- Early-momentum radar.
- Stock DNA.
- Why Buy / Why Not Buy.
- Clean validated stock cards with trade plan.
- Broker-style utilities below the decision-support layer.

## Phase 5 — Charts
- Stock and index charts.
- Detailed analysis popup.
- Heikin-Ashi presentation where appropriate.

## Phase 6 — AI/backend
- Keep AI Assistant environment-variable naming consistent with deployed configuration.
- Verify the code's expected variable and support the current `newsdata` deployment name without exposing secrets.

## Phase 7 — Performance/deployment validation
- Validate Render startup, scan latency, empty-data behavior, API failures and UI loading states.
- Merge only after verification.
