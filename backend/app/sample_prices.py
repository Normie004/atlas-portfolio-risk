"""Deterministic 65-business-day SYNTHETIC history for demos and offline tests."""
from datetime import date, timedelta
from decimal import Decimal
from .sample import SAMPLE


def sample_price_rows():
    end = date(2026, 10, 20)  # fixed reference date for reproducible offline demo
    days = []
    cursor = end
    while len(days) < 65:
        if cursor.weekday() < 5:
            days.append(cursor)
        cursor -= timedelta(days=1)
    days.reverse()
    rows = []
    for idx, d in enumerate(days):
        for asset_num, h in enumerate(SAMPLE['holdings']):
            if h['asset_class'] == 'Cash':
                continue
            base = Decimal(h['price'])
            drift = Decimal('1') + Decimal(idx - 64) * Decimal('0.00055') * Decimal((asset_num % 3) + 1)
            wave = Decimal(((idx * 7 + asset_num * 11) % 19) - 9) * Decimal('0.0008')
            price = (base * (drift + wave)).quantize(Decimal('0.0001'))
            rows.append({'date':d.isoformat(), 'symbol': h['symbol'], 'currency':h['currency'], 'close':str(price)})
    return {'source':'Deterministic synthetic daily closes (offline demo)', 'prices':rows, 'observation_dates':len(days)}
