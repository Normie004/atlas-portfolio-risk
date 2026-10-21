"""Historical *price-only* CAD mark-to-market analytics.

This is a fixed-quantity, buy-and-hold snapshot valuation; it does not model
trading, dividends, adjusted prices, corporate actions or total returns.
"""
from __future__ import annotations

import csv
import io
from datetime import date
from decimal import Decimal, InvalidOperation, ROUND_HALF_UP
from math import sqrt
from statistics import stdev

from pydantic import BaseModel, Field, field_validator

from .models import AnalyzeRequest

MAX_ROWS = 20_000
MAX_CSV_BYTES = 2 * 1024 * 1024


class HistoricalDataError(ValueError):
    pass


class PriceRow(BaseModel):
    date: date
    symbol: str = Field(min_length=1, max_length=24)
    currency: str
    close: Decimal = Field(gt=0, lt=Decimal('1000000000'))

    @field_validator('currency')
    @classmethod
    def currency_supported(cls, value: str):
        if value not in {'CAD', 'USD'}:
            raise ValueError('Price currency must be CAD or USD.')
        return value

    @field_validator('close')
    @classmethod
    def finite_price(cls, value: Decimal):
        if not value.is_finite():
            raise ValueError('Prices must be finite.')
        return value


class PriceHistoryRequest(BaseModel):
    portfolio: AnalyzeRequest
    prices: list[PriceRow] = Field(min_length=1, max_length=MAX_ROWS)
    source: str = Field(min_length=1, max_length=120)
    use_official_fx: bool = True


def parse_price_csv(raw: bytes) -> list[dict]:
    if len(raw) > MAX_CSV_BYTES:
        raise HistoricalDataError('Historical price CSV exceeds 2 MB.')
    try:
        decoded = raw.decode('utf-8-sig')
        reader = csv.DictReader(io.StringIO(decoded, newline=''))
        required = {'date', 'symbol', 'currency', 'close'}
        if reader.fieldnames is None or not required.issubset(reader.fieldnames):
            raise HistoricalDataError('Expected CSV columns: date,symbol,currency,close')
        rows = []
        seen = set()
        for row in reader:
            if len(rows) >= MAX_ROWS:
                raise HistoricalDataError('Maximum 20,000 historical price observations.')
            clean = {key: (value or '').strip() for key, value in row.items() if key is not None}
            try:
                validated = PriceRow.model_validate(clean)
            except Exception as exc:
                raise HistoricalDataError(f'Invalid historical price row {len(rows)+2}: {exc}') from exc
            ticker = validated.symbol.upper()
            key = (validated.date, ticker)
            if key in seen:
                raise HistoricalDataError(f'Duplicate historical price on {validated.date} for {ticker}.')
            seen.add(key)
            rows.append({'date': validated.date.isoformat(), 'symbol': ticker, 'currency': validated.currency, 'close': str(validated.close)})
    except UnicodeDecodeError as exc:
        raise HistoricalDataError('CSV must be UTF-8.') from exc
    if not rows:
        raise HistoricalDataError('Historical price CSV has no rows.')
    return rows


def _as_float(value: Decimal, places='0.01') -> float:
    return float(value.quantize(Decimal(places), rounding=ROUND_HALF_UP))


def _fx_by_date(observations: list[dict], days: set[date]) -> dict[date, Decimal]:
    """Prior known business-day close FX; never use a future quote.

    For cross-market holidays, one may carry a past known FX rate for <= 5 days.
    """
    rates = {}
    for row in observations:
        d = date.fromisoformat(str(row['date']))
        rate = Decimal(str(row['usd_to_cad']))
        if not rate.is_finite() or not Decimal('0') < rate < Decimal('10'):
            raise HistoricalDataError('Invalid historical FX rate supplied.')
        if d in rates:
            raise HistoricalDataError('Duplicate FX observation date.')
        rates[d] = rate
    sorted_fx_dates = sorted(rates)
    if not sorted_fx_dates:
        raise HistoricalDataError('No published FX observations.')
    fx_on_days = {}
    idx = -1
    for day in sorted(days):
        while idx + 1 < len(sorted_fx_dates) and sorted_fx_dates[idx + 1] <= day:
            idx += 1
        if idx >= 0 and (day - sorted_fx_dates[idx]).days <= 5:
            fx_on_days[day] = rates[sorted_fx_dates[idx]]
    return fx_on_days


def compute_price_history(payload: PriceHistoryRequest, fx_observations: list[dict] | None = None) -> dict:
    """Revalue today's fixed units through observed daily closes in each security's currency.

    Missing market dates use an INTERSECTION, not forward-filled asset prices.
    USD FX is backward-carried up to 5 days for differing market holidays.
    """
    portfolio = payload.portfolio
    holdings = portfolio.holdings
    priced = [h for h in holdings if h.asset_class != 'Cash' and h.quantity > 0]
    if not priced:
        raise HistoricalDataError('Include at least one non-cash holding for historical prices.')
    if len({h.symbol.upper() for h in priced}) != len(priced):
        raise HistoricalDataError('Portfolio has duplicate active symbols; aggregate quantities first.')
    priced_by_symbol = {h.symbol.upper(): h for h in priced}
    histories: dict[str, dict[date, Decimal]] = {sym: {} for sym in priced_by_symbol}
    for row in payload.prices:
        sym = row.symbol.upper()
        if sym not in priced_by_symbol:
            continue
        holding = priced_by_symbol[sym]
        if row.currency != holding.currency:
            raise HistoricalDataError(f'{sym} price currency {row.currency} does not match portfolio currency {holding.currency}.')
        if row.date in histories[sym]:
            raise HistoricalDataError(f'Duplicate price for {sym} on {row.date}.')
        histories[sym][row.date] = row.close
    missing = [sym for sym, history in histories.items() if not history]
    if missing:
        raise HistoricalDataError('Missing historical prices for: ' + ', '.join(missing))
    common_days = set.intersection(*(set(history) for history in histories.values()))
    if len(common_days) < 5:
        raise HistoricalDataError('Need at least five shared price dates across all active symbols.')

    has_usd = any(h.currency == 'USD' and h.quantity > 0 for h in holdings)
    if has_usd and payload.use_official_fx:
        if fx_observations is None:
            raise HistoricalDataError('Published USD/CAD history is required for USD holdings.')
        fx_values = _fx_by_date(fx_observations, common_days)
        common_days &= set(fx_values)
    else:
        fx_values = {day: portfolio.usd_to_cad for day in common_days}
    if len(common_days) < 5:
        raise HistoricalDataError('Fewer than five dates align across security prices and available FX history.')

    observations = []
    exact_values = []
    for day in sorted(common_days):
        fx = fx_values[day]
        total = Decimal('0')
        for h in priced:
            close = histories[h.symbol.upper()][day]
            total += h.quantity * close * (fx if h.currency == 'USD' else Decimal('1'))
        for h in holdings:
            if h.asset_class == 'Cash':
                total += h.quantity * h.price * (fx if h.currency == 'USD' else Decimal('1'))
        if total <= 0:
            raise HistoricalDataError('Portfolio value must be positive for every observation.')
        exact_values.append(total)
        observations.append({'date': day.isoformat(), 'value_cad': _as_float(total), 'usd_to_cad': float(fx)})
    returns = [float(exact_values[i] / exact_values[i-1] - 1) for i in range(1, len(exact_values))]
    vol = (stdev(returns) * sqrt(252) * 100) if len(returns) > 1 else None
    peak = exact_values[0]
    worst_dd = Decimal('0')
    for v in exact_values:
        peak = max(peak, v)
        worst_dd = min(worst_dd, v / peak - 1)
    first, last = exact_values[0], exact_values[-1]
    changes = (last / first - 1) * 100
    return {
        'source': payload.source,
        'valuation_basis': 'Fixed quantities × daily raw closing prices, converted to CAD',
        'fx_basis': ('Published Bank of Canada USD/CAD observations (carry last known rate <=5 days)'
                     if has_usd and payload.use_official_fx else 'Fixed user-supplied USD/CAD rate'),
        'first_date': observations[0]['date'],
        'last_date': observations[-1]['date'],
        'observation_count': len(observations),
        'symbols': sorted(priced_by_symbol),
        'start_value_cad': _as_float(first),
        'end_value_cad': _as_float(last),
        'price_only_change_pct': _as_float(changes),
        'price_only_annualized_volatility_pct': round(vol, 2) if vol is not None else None,
        'price_only_max_drawdown_pct': _as_float(worst_dd * 100),
        'observations': observations,
        'methodology': (
            'Fixed current quantities with closing-price changes; cash is constant in its native currency. '
            'Price dates are intersected across securities; holidays may be excluded. When official FX is enabled, '
            'the most recent published USD/CAD at or before the price date is used, no more than five days old. '
            'Returns are close-to-close price-only CAD valuation changes, NOT total returns or a trade backtest. '
            'Raw closes are not dividend/split adjusted; corporate actions, income, fees and rebalancing are excluded.'
        ),
    }
