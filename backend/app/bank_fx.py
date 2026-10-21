"""Bank of Canada Valet FX ingestion with validation and an in-memory TTL cache.

Bank of Canada FXUSDCAD is CAD per 1 USD, published on business days.
No fallback to synthetic rates on an upstream failure.
"""
from __future__ import annotations

from datetime import date, datetime, timezone
from decimal import Decimal, InvalidOperation
from threading import Lock
import time

import httpx

FX_URL = 'https://www.bankofcanada.ca/valet/observations/FXUSDCAD/json'
SOURCE_URL = 'https://www.bankofcanada.ca/valet-api-how-to/'
TTL_SECONDS = 12 * 60 * 60
_cache: dict[int, tuple[float, dict]] = {}
_cache_lock = Lock()


class FXUnavailable(Exception):
    """No valid authoritative FX observations are currently available."""


def parse_observations(body: dict) -> list[dict]:
    """Validate Bank of Canada Valet observations, preserving the observation date.

    Partial/missing non-trading-day observations are ignored. The entire
    response is rejected if there are no usable observations.
    """
    if not isinstance(body, dict):
        raise FXUnavailable('The Bank of Canada returned an unexpected response.')
    raw = body.get('observations')
    if not isinstance(raw, list):
        raise FXUnavailable('The Bank of Canada returned an unexpected response.')
    observations: dict[str, Decimal] = {}
    for row in raw:
        if not isinstance(row, dict):
            continue
        field = row.get('FXUSDCAD')
        if not isinstance(field, dict) or 'v' not in field:
            continue
        try:
            day = date.fromisoformat(row['d']).isoformat()
            rate = Decimal(str(field['v']))
        except (ValueError, TypeError, KeyError, InvalidOperation):
            raise FXUnavailable('The Bank of Canada provided an invalid observation.')
        if not rate.is_finite() or not Decimal('0') < rate < Decimal('10'):
            raise FXUnavailable('The Bank of Canada provided an invalid USD/CAD rate.')
        if day in observations:
            raise FXUnavailable('The Bank of Canada provided a duplicate observation date.')
        observations[day] = rate
    if not observations:
        raise FXUnavailable('No usable USD/CAD observations were returned.')
    return [{'date': day, 'usd_to_cad': str(value)} for day, value in sorted(observations.items())]


def fetch_fx_history(days: int = 90) -> dict:
    """Return the latest N published observations (not N calendar days)."""
    if not 2 <= days <= 365:
        raise ValueError('Days must be between 2 and 365.')
    with _cache_lock:
        cached = _cache.get(days)
        if cached and time.monotonic() - cached[0] < TTL_SECONDS:
            return {**cached[1], 'cache_status': 'hit'}

    try:
        with httpx.Client(timeout=8.0, follow_redirects=False) as client:
            resp = client.get(FX_URL, params={'recent': days})
            resp.raise_for_status()
            body = resp.json()
        observations = parse_observations(body)
    except FXUnavailable:
        raise
    except (httpx.HTTPError, ValueError, TypeError) as exc:
        raise FXUnavailable('Could not retrieve Bank of Canada data. Try again later or use your manual FX rate.') from exc
    latest = observations[-1]
    result = {
        'source': 'Bank of Canada Valet API',
        'source_url': SOURCE_URL,
        'series': 'FXUSDCAD',
        'unit': 'CAD per 1 USD',
        'observation_date': latest['date'],
        'latest_usd_to_cad': latest['usd_to_cad'],
        'retrieved_at_utc': datetime.now(timezone.utc).isoformat(),
        'observations': observations,
    }
    with _cache_lock:
        _cache[days] = (time.monotonic(), result)
    return {**result, 'cache_status': 'miss'}
