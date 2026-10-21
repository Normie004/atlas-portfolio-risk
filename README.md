# ATLAS — Portfolio Risk & Trading Operations Platform

A project for learning institutional-style portfolio valuation, currency exposure, and hypothetical stress scenarios. **This is a demo application, not an investment recommendation or production risk system.** The bundled prices and reference USD/CAD rate are entirely **synthetic**.

## Version 0.2 — what works

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
- Base USD/CAD demo FX defaults to 1.37, which is **not a live rate**. Update it on the dashboard.
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

## Planned stages

- **v0.3:** Bank of Canada Valet FX integration with rate timestamps and caching; licensed historical market price ingestion
- **v0.4:** Docker, PostgreSQL, CI/CD, more tests, deployment
- **v0.5:** Source-grounded AI analyst explaining quantitative results

### Engineering standards to add before claiming 'production-ready'

Authentication, per-user portfolios, secrets management, auditable events, robust handling of market holidays, price timestamps and stale data, instrument identifiers, pricing of bonds and derivatives, calculation methodology validation, load testing, observability, and deployment security.

## Why this project exists

To bridge real engineering skills (ETL, validation, automation, APIs) with investment questions (currency exposure, stress testing, trade operations) in one demonstrable application.

## Publishing to GitHub

If the GitHub repository is empty, from the `atlas-starter` folder run:

```bash
git init
git add .
git commit -m "Build ATLAS v0.2 dashboard and reconciliation engine"
git branch -M main
git remote add origin https://github.com/Normie004/atlas-portfolio-risk.git
git push -u origin main
```

`.gitignore` excludes virtual environments, local node packages, caches and build output. Do not commit keys or .env files.
