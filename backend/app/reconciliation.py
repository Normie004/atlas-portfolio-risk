"""Deterministic paper trade processing and independent position/cash reconciliation.

No orders leave the process; this module does not connect to brokers or place trades.
All ledger calculations use Decimal. Rejected rows do not affect balances.
"""
from decimal import Decimal
from typing import Literal
from pydantic import BaseModel, Field, field_validator

Currency = Literal['CAD', 'USD']


class Trade(BaseModel):
    trade_id: str = Field(min_length=1, max_length=40)
    symbol: str = Field(min_length=1, max_length=24)
    side: Literal['BUY', 'SELL']
    quantity: Decimal = Field(gt=0)
    price: Decimal = Field(ge=0)
    currency: Currency
    fee: Decimal = Field(default=Decimal('0'), ge=0)

    @field_validator('trade_id', 'symbol')
    @classmethod
    def trimmed(cls, value: str):
        if not value.strip():
            raise ValueError('Must not be blank')
        return value.strip()


class LedgerPosition(BaseModel):
    symbol: str = Field(min_length=1, max_length=24)
    currency: Currency
    quantity: Decimal = Field(ge=0)


class ReconcileRequest(BaseModel):
    opening_positions: list[LedgerPosition] = Field(max_length=500)
    opening_cash: dict[Currency, Decimal]
    trades: list[Trade] = Field(max_length=1000)
    reported_positions: list[LedgerPosition] = Field(max_length=500)
    reported_cash: dict[Currency, Decimal]

    @field_validator('opening_cash', 'reported_cash')
    @classmethod
    def nonnegative_cash(cls, balances):
        if any(value < 0 for value in balances.values()):
            raise ValueError('Cash balances must be nonnegative')
        return balances


def reconcile(request: ReconcileRequest) -> dict:
    """Apply *paper* transactions, then compare derived balances to reported balances.

    An unknown instrument, oversell, cash shortfall, duplicate trade id, or currency
    mismatch is recorded as an exception and skipped. No execution takes place.
    """
    positions: dict[tuple[str, str], Decimal] = {}
    issues: list[dict] = []
    event_log: list[dict] = []

    for item in request.opening_positions:
        key = (item.symbol.upper(), item.currency)
        if key in positions:
            raise ValueError(f'Duplicate opening position {item.symbol}/{item.currency}')
        positions[key] = item.quantity

    cash = {'CAD': request.opening_cash.get('CAD', Decimal('0')),
            'USD': request.opening_cash.get('USD', Decimal('0'))}
    seen_ids: set[str] = set()
    accepted = 0

    def exception(code: str, detail: str, trade_id: str | None = None):
        issues.append({'code': code, 'trade_id': trade_id, 'detail': detail})

    for trade in request.trades:
        key = (trade.symbol.upper(), trade.currency)
        gross = trade.quantity * trade.price
        outcome: str | None = None
        if trade.trade_id in seen_ids:
            outcome = 'DUPLICATE_TRADE_ID'
        else:
            seen_ids.add(trade.trade_id)
            if key not in positions:
                outcome = 'UNKNOWN_INSTRUMENT'
            elif trade.side == 'SELL' and positions[key] < trade.quantity:
                outcome = 'INSUFFICIENT_POSITION'
            elif trade.side == 'BUY' and cash[trade.currency] < gross + trade.fee:
                outcome = 'INSUFFICIENT_CASH'
        if outcome is not None:
            exception(outcome, f'{trade.side} {trade.quantity} {trade.symbol} was not applied: {outcome.lower().replace("_", " ")}', trade.trade_id)
            event_log.append({'trade_id': trade.trade_id, 'symbol': trade.symbol,
                              'side': trade.side, 'status': 'REJECTED', 'reason': outcome})
            continue
        if trade.side == 'BUY':
            positions[key] += trade.quantity
            cash[trade.currency] -= gross + trade.fee
        else:
            positions[key] -= trade.quantity
            cash[trade.currency] += gross - trade.fee
        accepted += 1
        event_log.append({'trade_id': trade.trade_id, 'symbol': trade.symbol,
                          'side': trade.side, 'status': 'APPLIED', 'reason': None})

    reported: dict[tuple[str, str], Decimal] = {}
    for item in request.reported_positions:
        key = (item.symbol.upper(), item.currency)
        if key in reported:
            raise ValueError(f'Duplicate reported position {item.symbol}/{item.currency}')
        reported[key] = item.quantity

    breaks: list[dict] = []
    for sym, ccy in sorted(set(positions) | set(reported)):
        expected = positions.get((sym, ccy), Decimal('0'))
        observed = reported.get((sym, ccy), Decimal('0'))
        difference = observed - expected
        if abs(difference) > Decimal('0.000001'):
            breaks.append({'type':'POSITION', 'key':sym, 'currency':ccy,
                           'expected': str(expected), 'reported':str(observed), 'difference':str(difference)})
    for ccy in ('CAD', 'USD'):
        expected = cash[ccy]
        observed = request.reported_cash.get(ccy, Decimal('0'))
        difference = observed - expected
        if abs(difference) > Decimal('0.01'):
            breaks.append({'type':'CASH', 'key':ccy, 'currency':ccy,
                           'expected':str(expected), 'reported':str(observed), 'difference':str(difference)})

    return {
        'data_status': 'Illustrative paper trades and supplied balances — no real executions',
        'trades_received': len(request.trades),
        'trades_applied': accepted,
        'trades_rejected': len(request.trades) - accepted,
        'break_count': len(breaks),
        'trade_exceptions': issues,
        'reconciliation_breaks': breaks,
        'audit_log': event_log,
        'expected_positions': [
            {'symbol':s, 'currency':c, 'quantity':str(q)}
            for (s,c),q in sorted(positions.items())
        ],
        'expected_cash': {ccy:str(balance) for ccy,balance in cash.items()},
        'methodology': [
            'Only simulated BUY and SELL trades are supported; no orders are sent to a broker.',
            'Trades are evaluated sequentially; repeated trade IDs and invalid transactions are ignored and flagged.',
            'BUY consumes native-currency cash; SELL reduces holdings and increases native-currency cash; fees reduce cash.',
            'Reported balances are independent external inputs, compared to calculated balances.',
            'This demo omits settlement timing, financing, short-selling, corporate actions, taxes and broker commissions beyond explicit fees.'
        ]
    }
