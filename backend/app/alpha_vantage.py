"""Optional raw close integration (credentials only on local backend).

TIME_SERIES_DAILY is raw/unadjusted, not total-return data. Source labels are
maintained throughout and endpoint failures never silently use fake prices.
"""
from __future__ import annotations

from datetime import date, datetime, timezone
from decimal import Decimal
import os
import re
import time
from threading import Lock
import httpx
from pathlib import Path
from dotenv import load_dotenv

load_dotenv(Path(__file__).resolve().parents[1] / '.env')

URL = 'https://www.alphavantage.co/query'
CACHE_TTL = 60 * 60 * 12
_cache: dict[str, tuple[float, list[dict]]] = {}
_lock = Lock()

# Explicit exchange qualification is essential: e.g. RY (NYSE/USD) != RY.TRT (TSX/CAD).
# This map is tailored only to the bundled demonstration portfolio, not arbitrary instruments.
SAMPLE_SYMBOLS = {'RY':'RY.TRT', 'SHOP':'SHOP.TRT', 'XBB':'XBB.TRT', 'AAPL':'AAPL', 'MSFT':'MSFT', 'BND':'BND'}


class MarketDataUnavailable(Exception):
    pass


def parse_daily_closes(body: dict, local_symbol: str, currency: str) -> list[dict]:
    if not isinstance(body, dict):
        raise MarketDataUnavailable(f'{local_symbol}: unexpected provider response.')
    for field in ('Error Message', 'Note', 'Information'):
        if body.get(field):
            raise MarketDataUnavailable(f'{local_symbol}: Alpha Vantage returned: {str(body[field])[:300]}')
    values = body.get('Time Series (Daily)')
    if not isinstance(values, dict) or len(values) < 5:
        raise MarketDataUnavailable(f'{local_symbol}: provider returned too few daily closes.')
    parsed = []
    for day, info in values.items():
        try:
            d = date.fromisoformat(day)
            close = Decimal(str(info['4. close']))
        except (ValueError, KeyError, TypeError) as exc:
            raise MarketDataUnavailable(f'{local_symbol}: invalid historical close.') from exc
        if not close.is_finite() or close <= 0:
            raise MarketDataUnavailable(f'{local_symbol}: invalid nonpositive price.')
        parsed.append({'date':d.isoformat(),'symbol':local_symbol,'currency':currency,'close':str(close)})
    return sorted(parsed, key=lambda x:x['date'])


def fetch_daily_prices(holdings) -> dict:
    key = os.getenv('ALPHAVANTAGE_API_KEY', '').strip()
    if not key:
        raise MarketDataUnavailable('Alpha Vantage key is not configured. Add ALPHAVANTAGE_API_KEY to backend/.env as described in README, or upload your own historical price CSV.')
    if key.lower() == 'demo':
        raise MarketDataUnavailable('Use your own Alpha Vantage key; the provider demo key cannot fetch all portfolio symbols.')
    active = [h for h in holdings if h.asset_class != 'Cash' and h.quantity > 0]
    if not active or len(active) > 8:
        raise MarketDataUnavailable('Requires 1 to 8 active non-cash positions (provider rate limits).')
    if len({h.symbol.upper() for h in active}) != len(active):
        raise MarketDataUnavailable('Duplicate portfolio ticker; aggregate holdings first.')
    if any(h.symbol.upper() not in SAMPLE_SYMBOLS for h in active):
        raise MarketDataUnavailable('For safety, this demo provider supports only RY, SHOP, AAPL, MSFT, XBB and BND with explicit exchange mapping. For other instruments, upload historical CSV with verified quote currencies.')
    prices = []
    for h in active:
        local_symbol = h.symbol.upper()
        provider_symbol = SAMPLE_SYMBOLS[local_symbol]
        # Never guess quote currency for a symbol: use only explicit trusted sample aliases.
        expected_currency = 'CAD' if provider_symbol.endswith('.TRT') else 'USD'
        if h.currency != expected_currency:
            raise MarketDataUnavailable(f'{local_symbol}: expected {expected_currency} based on provider exchange mapping, but portfolio says {h.currency}.')
        cache_key = provider_symbol
        with _lock:
            cached = _cache.get(cache_key)
        if cached and time.monotonic() - cached[0] <= CACHE_TTL:
            prices.extend(cached[1])
            continue
        try:
            with httpx.Client(timeout=12, follow_redirects=False) as client:
                resp = client.get(URL, params={'function':'TIME_SERIES_DAILY','symbol':provider_symbol,'outputsize':'compact','apikey':key})
                resp.raise_for_status()
                body = resp.json()
        except (httpx.HTTPError, ValueError) as exc:
            raise MarketDataUnavailable(f'{local_symbol}: could not fetch Alpha Vantage daily closes.') from exc
        parsed = parse_daily_closes(body, local_symbol, expected_currency)
        with _lock:
            _cache[cache_key] = (time.monotonic(), parsed)
        prices.extend(parsed)
    return {
        'source': 'Alpha Vantage TIME_SERIES_DAILY raw unadjusted closes (provider, not live)',
        'source_url':'https://www.alphavantage.co/documentation/#daily',
        'retrieved_at_utc':datetime.now(timezone.utc).isoformat(),
        'symbol_map':{h.symbol.upper():SAMPLE_SYMBOLS[h.symbol.upper()] for h in active},
        'prices': prices,
    }
