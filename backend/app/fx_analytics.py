"""Fixed-holdings FX translation history. This is NOT portfolio backtesting."""
from __future__ import annotations

from decimal import Decimal, ROUND_HALF_UP
from math import sqrt
from statistics import stdev

from .models import AnalyzeRequest


def _rounded(n: Decimal) -> float:
    return float(n.quantize(Decimal('0.01'), rounding=ROUND_HALF_UP))


def fx_translation_history(request: AnalyzeRequest, fx_data: dict) -> dict:
    """Hold quantities/native prices constant; only vary USD-to-CAD FX rates.

    Volatility/drawdown refer to *FX translation only* and cannot be interpreted
    as historical portfolio returns or risk of the full portfolio.
    """
    cad_native = sum((p.quantity * p.price for p in request.holdings if p.currency == 'CAD'), Decimal('0'))
    usd_native = sum((p.quantity * p.price for p in request.holdings if p.currency == 'USD'), Decimal('0'))
    values = []
    for row in fx_data['observations']:
        fx = Decimal(row['usd_to_cad'])
        values.append({'date': row['date'], 'usd_to_cad': float(fx), 'value_cad': _rounded(cad_native + usd_native * fx)})
    if not values:
        raise ValueError('No FX observations are available.')
    # Calculate daily FX-only portfolio returns using unrounded CAD values.
    raw_values = [cad_native + usd_native * Decimal(row['usd_to_cad']) for row in fx_data['observations']]
    if any(v <= 0 for v in raw_values):
        raise ValueError('Portfolio must have a positive total market value.')
    daily_returns = [float(raw_values[i] / raw_values[i-1] - 1) for i in range(1, len(raw_values))]
    volatility_pct = stdev(daily_returns) * sqrt(252) * 100 if len(daily_returns) >= 2 else None
    peak = raw_values[0]
    max_drawdown = Decimal('0')
    for value in raw_values:
        peak = max(peak, value)
        max_drawdown = min(max_drawdown, value / peak - 1)
    latest_total = raw_values[-1]
    usd_exposure_pct = usd_native * Decimal(fx_data['latest_usd_to_cad']) / latest_total * 100
    return {
        'source': fx_data['source'], 'source_url': fx_data['source_url'],
        'series': 'FXUSDCAD', 'observation_date': fx_data['observation_date'],
        'retrieved_at_utc': fx_data['retrieved_at_utc'], 'cache_status': fx_data['cache_status'],
        'latest_usd_to_cad': float(Decimal(fx_data['latest_usd_to_cad'])),
        'observations': values, 'latest_value_cad': _rounded(latest_total),
        'fx_only_change_pct': _rounded((raw_values[-1] / raw_values[0] - 1) * 100),
        'fx_only_annualized_volatility_pct': round(volatility_pct, 2) if volatility_pct is not None else None,
        'fx_only_max_drawdown_pct': _rounded(max_drawdown * 100),
        'usd_exposure_pct': _rounded(usd_exposure_pct),
        'methodology': ('All native-currency asset prices and quantities are frozen at the supplied snapshot. '
                        'Only published USD/CAD conversion rates change. Not total-return performance, '
                        'a portfolio backtest, or an institutional VaR model.'),
    }
