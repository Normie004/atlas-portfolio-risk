# ATLAS — Portfolio Risk & Trading Operations Platform

A project for learning institutional-style portfolio valuation, currency exposure, trade reconciliation and historical price-only risk analysis. **This is an educational application, not investment advice or a production trading/risk system.** The bundled spot and historical prices are **synthetic**. Optional integrations support official published Bank of Canada USD/CAD rates and Alpha Vantage historical raw closes using your own API key.

## Version 0.4 — what works

- FastAPI backend with a validated holdings input model
- React + TypeScript dark-mode dashboard
- Asset allocation and CAD/USD currency exposure
- Portfolio valuation in CAD using an editable USD/CAD conversion factor
- Hypothetical equity, bond and USD currency shocks
- Upload a CSV of holdings and recalculate risk
- Backend tests for FX conversion, scenarios, bad input and upload format
- Paper-trade blotter with validated BUY/SELL instructions and native-currency cash impact
- Duplicate trade-ID detection, insufficient-position and insufficient-cash checks
- Independent position and cash balance reconciliation, exception reporting, and transaction audit log
- Editable reported balances on the React dashboard to demonstrate reconciling or clearing breaks
- Bank of Canada Valet API integration (`FXUSDCAD`), including the official observation date and a 12-hour in-memory cache
- FX translation-only history chart, annualized FX-only value volatility, and FX-only maximum drawdown
- Optional one-click application of the latest published USD/CAD rate to the existing portfolio overview; manual rate remains supported
- **New v0.4:** historical security closing-price CSV ingestion, currency and duplicate validation, common-date reconciliation
- Historical portfolio mark-to-market with fixed quantities, daily price-only CAD value changes, annualized realized volatility and maximum drawdown
- Explicit FX choice: fixed local input rate or published Bank of Canada historical observations, with prior-date lookback (no future FX)
- Reproducible **synthetic 65-day history** to try the engine without an API key
- **Optional** Alpha Vantage `TIME_SERIES_DAILY` raw historical close API with a **private local-only** key, explicit TSX vs US-exchange mapping for demo symbols, 12-hour in-memory caching and no silent synthetic fallback
- 45 backend tests covering portfolio, reconciliation, currency, historical metrics and data ingestion

## 1. Prerequisites (Mac)

- Python 3.11 or newer — `python3 --version`
- Node 20.19+ or 22.12+ — `node --version` (see https://vite.dev/guide/)
- VS Code recommended, but not required

## 2. Start backend (Terminal 1)

```bash
cd atlas-starter/backend
python3 -m venv .venv
source .venv/bin/activate
python -m pip install -r requirements.txt
python -m uvicorn app.main:app --reload --port 8000
```

Backend docs: http://127.0.0.1:8000/docs

## 3. Start frontend (Terminal 2)

```bash
cd atlas-starter/frontend
npm install
npm run dev
```

Open http://127.0.0.1:5173

If your project folder is inside Desktop/Downloads, substitute the correct full directory path in the `cd` commands. For example, in Terminal 1 `cd ~/Downloads/atlas-starter/backend`.

## 4. Run tests (Terminal 3 or after stopping backend)

```bash
cd atlas-starter/backend
source .venv/bin/activate
python -m pytest -q
```

## 5. Try your own portfolio CSV

See `data/sample_portfolio.csv`. The required columns are:

```csv
symbol,name,asset_class,currency,quantity,price
AAPL,Apple demo,Equity,USD,10,200
SHOP,Shopify demo,Equity,CAD,5,100
```

- `asset_class`: `Equity`, `Bond`, `ETF`, or `Cash`.
- `currency`: `CAD` or `USD`.
- `quantity`, `price`: nonnegative numeric values; total portfolio value must be positive.
- Values are based **only on prices you supply**, not live prices.
- Base USD/CAD demo FX defaults to 1.37, which is **not a live rate**. Update it manually or click the official FX history button to load the latest *published* Bank of Canada rate. The observation date is displayed.
- For this initial version, portfolio weights are long-only; no leverage, derivatives, short positions, accrued income, fees or real-time execution.
- FX shock is relative to the USD value in CAD; e.g. -10% means 10% lower CAD value per USD.

## What the simplified scenario calculation means

For a USD equity position:

```
value_CAD = quantity * price_USD * USD_to_CAD
stressed_value_CAD = quantity * price_USD * (1 + equity_shock_pct / 100)
                     * USD_to_CAD * (1 + USD_fx_shock_pct / 100)
scenario_P&L = stressed_value_CAD - value_CAD
```

This is a deterministic scenario, not a calibrated VaR/stress engine. Cash is fixed in its native currency; USD cash moves with USD/CAD.

## Reconciliation lab (v0.2)

Scroll down to **Trade blotter & reconciliation** in the dashboard. The demo contains six synthetic trade rows: three valid trades and three rejected instructions (duplicate trade ID, oversell, insufficient cash). It also deliberately supplies one incorrect position and one incorrect cash balance.

1. Click **Run reconciliation** to compare supplied positions/cash with independently calculated balances.
2. Change the reported AAPL quantity or USD cash amount and click Run again.
3. Click **Match calculated** to show zero reconciliation breaks (rejected trade instructions remain flagged).
4. Click **Reset demo** to reload the original incorrect reported data.

Relevant API routes: `GET /api/trades/sample` and `POST /api/trades/reconcile`.
All transactions are simulations. No orders are placed; there is no brokerage account or live trade integration.

## FX history & official exchange rates (v0.3)

Scroll to **Bank of Canada FX monitor** in the dashboard. Press **Load official FX history**, select 30, 90, or 180 observations, and optionally press **Use published FX rate in overview** to update the portfolio's CAD valuation and stress-test calculations. This leaves the asset prices untouched.

- Data source: [Bank of Canada Valet API](https://www.bankofcanada.ca/valet-api-how-to/), series `FXUSDCAD` (Canadian dollars per US dollar).
- Published daily observations are *not* streaming/real-time FX quotes. The observation date is shown; weekends and holidays may have no observation.
- The backend caches each observation window for 12 hours to avoid unnecessary requests.
- If the API is unavailable, ATLAS displays an error and **does not silently substitute a synthetic exchange rate**.
- **Critical methodological limitation:** historical FX translation freezes today's quantities and native-currency asset prices and changes **only** the USD/CAD conversion rate. Annualized volatility and drawdown describe *FX translation of that static snapshot only*. They are **not** historical investment returns, backtesting, or the total portfolio risk.
- API: `GET /api/fx/usd-cad` and `POST /api/fx/translation-history?days=90` (same JSON body as `POST /api/analyze`).
- No API key or account required. Internet access is required for these new endpoints.

## Historical price & portfolio risk lab (v0.4)

Scroll to **Historical price & portfolio risk lab**. Click **Load synthetic historical demo** first; this loads 65 deterministic demonstration price dates for the original six non-cash holdings and calculates a fixed-holdings CAD valuation history using the editable overview FX rate. Synthetic results are clearly labelled.

To ingest real user-licensed daily prices, choose **Import historical prices CSV**. Required columns:

```csv
date,symbol,currency,close
2026-10-15,AAPL,USD,250.12
2026-10-16,AAPL,USD,252.51
2026-10-15,MSFT,USD,510.20
2026-10-16,MSFT,USD,513.10
```

*Numbers above are format examples, not asserted market observations. At least five shared daily observations are needed for **every** non-cash instrument in your current portfolio; sample rows alone cannot produce a calculation. Prices must have the correct quote currency. Download valid data only from a provider whose terms permit your use.*

To use the optional Alpha Vantage integration:

1. Request a personal key on [Alpha Vantage's support page](https://www.alphavantage.co/support/#api-key). Their free plan has a 25-API-requests-per-day published limit and raw daily close data is available with the compact output (about 100 daily closes per symbol).
2. In your **Mac's own project folder**, create `backend/.env` from `backend/.env.example` and replace `your_personal_key_here` with your personal key. **Never send the key to ChatGPT or commit it to GitHub.** `.gitignore` excludes `.env` and `.env.*` (except the sample file).
3. Install the updated backend requirements (`python -m pip install -r requirements.txt`) and restart FastAPI. Refresh the dashboard; its provider status should show **API key configured**.
4. Click **Fetch Alpha Vantage closes**. Each eligible non-cash holding uses a separate provider request, which consumes your personal quota; a quota error will be shown explicitly. This demo permits six symbols only: `RY` (maps to `RY.TRT`), `SHOP` (`SHOP.TRT`), `XBB` (`XBB.TRT`), `AAPL`, `MSFT`, `BND`. The direct provider map is restricted intentionally, to avoid silently mixing NYSE RY/USD with TSX RY/CAD. The provider's quote availability is not guaranteed; upload a CSV when unsupported or rate-limited.
5. Alpha Vantage loads *raw, unadjusted* closes. For USD holdings, ATLAS will also request published Bank of Canada FX history; it fails visibly if either external source is unavailable. The overview's snapshot numbers are still separate from historical source data.

**Historical methodology and limitations**

- `value_CAD(t) = Σ fixed_quantity × raw_close(t) × USD/CAD(t) + native_cash_valued_in_CAD(t)`.
- All non-cash symbols must share at least five dates; the engine uses their **intersection** and never fabricates missing security closes. For currency conversion, an official published FX observation at or before each date (up to five calendar days prior) can be used; future rates are never used.
- `price_only_change_pct = (ending_value / starting_value − 1) × 100`.
- `annualized_volatility_pct = stddev(sample_daily_value_changes) × sqrt(252) × 100`.
- `max_drawdown_pct = min(value_t / max(value_0 ... value_t) − 1) × 100`.
- Values describe today's **fixed quantities** repriced through past raw closes and optional published FX rates. They are *not* your portfolio's realized P&L, total returns, dividends-adjusted returns, a transaction-level backtest or forecast. Splits, dividends, coupon/accrued interest, fees, rebalancing, and benchmark/risk-free adjustments are excluded. The Bond category is supported as a simplified market-price instrument; it is not a bond yield/interest-rate pricing model.
- API routes: `GET /api/history/sample`, `POST /api/history/upload`, `POST /api/history/analyze`, `POST /api/history/alpha-vantage`, `GET /api/history/market-status`. The Alpha Vantage key is never returned to the browser; do not deploy these unauthenticated example endpoints to a public server.

## Planned stages

- **v0.5:** PostgreSQL, Docker, CI/CD and automated frontend build; better market-data provenance, adjusted price and corporate-action methodology
- **v0.6:** Source-grounded AI analyst explaining quantitative results

### Engineering standards to add before claiming 'production-ready'

Authentication, per-user portfolios, secrets management, auditable events, robust handling of market holidays, price timestamps and stale data, instrument identifiers, pricing of bonds and derivatives, calculation methodology validation, load testing, observability, and deployment security.

## Why this project exists

To bridge real engineering skills (ETL, validation, automation, APIs) with investment questions (currency exposure, stress testing, trade operations) in one demonstrable application.

## Publishing updates to GitHub

Your repository already exists at `Normie004/atlas-portfolio-risk`. Open GitHub Desktop, confirm that the ATLAS folder is selected, inspect the changed files, enter a summary such as `Add historical price-only portfolio risk analytics`, click **Commit to main**, then **Push origin**. Never commit keys or `.env` files.

`.gitignore` excludes virtual environments, local node packages, caches and build output.
