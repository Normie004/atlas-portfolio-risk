from collections import defaultdict
from decimal import Decimal, ROUND_HALF_UP
from .models import AnalyzeRequest, Holding

ONE = Decimal('1')
HUNDRED = Decimal('100')
ZERO = Decimal('0')
CENT = Decimal('0.01')


def n(value: Decimal, places: Decimal = CENT) -> float:
    return float(value.quantize(places, rounding=ROUND_HALF_UP))


def analyze(request: AnalyzeRequest) -> dict:
    """Price-based portfolio valuation, exposure aggregation and *hypothetical* shock analysis.

    P&L here is a single-step mark-to-scenario estimate, NOT a forecast, risk model,
    VaR measure, stress backtest or order execution system.
    """
    fx = request.usd_to_cad
    shocked_fx = fx * (ONE + request.scenario.usd_fx_pct / HUNDRED)
    by_asset: dict[str, Decimal] = defaultdict(Decimal)
    by_currency: dict[str, Decimal] = defaultdict(Decimal)
    rows = []
    total = ZERO
    stressed_total = ZERO

    for h in request.holdings:
        native = h.quantity * h.price
        conversion = fx if h.currency == 'USD' else ONE
        cad_value = native * conversion
        pct_shock = (request.scenario.equities_pct if h.asset_class in ('Equity', 'ETF')
                     else request.scenario.bonds_pct if h.asset_class == 'Bond' else ZERO)
        # Cash's nominal price is fixed here. USD cash still has FX movement.
        shocked_native = native * (ONE + pct_shock / HUNDRED)
        stressed_cad = shocked_native * (shocked_fx if h.currency == 'USD' else ONE)
        pnl = stressed_cad - cad_value
        total += cad_value
        stressed_total += stressed_cad
        by_asset[h.asset_class] += cad_value
        by_currency[h.currency] += cad_value
        rows.append({
            'symbol':h.symbol, 'name':h.name, 'asset_class':h.asset_class,
            'currency':h.currency, 'quantity':str(h.quantity),
            'price':str(h.price), 'value_cad':n(cad_value),
            'scenario_pnl_cad':n(pnl), '_precise_value_cad':cad_value
        })

    if total <= ZERO:
        raise ValueError('Portfolio must have a positive total market value')

    for row in rows:
        # Preserve each row's exact valuation even if the input repeats a ticker.
        precise = row.pop('_precise_value_cad')
        row['weight_pct'] = n(precise / total * HUNDRED)

    rows.sort(key=lambda x: x['value_cad'], reverse=True)
    scenario_delta = stressed_total - total
    return {
        'source_label': request.source_label,
        'data_status':'Demo / user-provided prices only — not live market data',
        'currency':'CAD',
        'usd_to_cad':float(fx),
        'total_value_cad':n(total),
        'scenario_value_cad':n(stressed_total),
        'scenario_pnl_cad':n(scenario_delta),
        'scenario_return_pct':n(scenario_delta / total * HUNDRED),
        'largest_position_pct':rows[0]['weight_pct'],
        'position_count':len(rows),
        'asset_exposures':[
            {'name':k, 'value_cad':n(v), 'weight_pct':n(v / total * HUNDRED)}
            for k,v in sorted(by_asset.items(), key=lambda x:x[1], reverse=True)
        ],
        'currency_exposures':[
            {'name':k, 'value_cad':n(v), 'weight_pct':n(v / total * HUNDRED)}
            for k,v in sorted(by_currency.items(), key=lambda x:x[1], reverse=True)
        ],
        'positions':rows,
        'scenario':{
            'equities_pct':float(request.scenario.equities_pct),
            'bonds_pct':float(request.scenario.bonds_pct),
            'usd_fx_pct':float(request.scenario.usd_fx_pct)
        },
        'assumptions': [
            'Input prices and FX rates are user-provided; the bundled sample is synthetic.',
            'Equity and ETF positions use the equity shock; bond positions use the bond shock.',
            'USD positions are revalued using the shocked USD/CAD exchange rate.',
            'Cash is fixed in nominal terms in its denomination, and no transaction costs apply.',
            'This simplified scenario is educational, not a prediction or institutional risk model.'
        ]
    }
