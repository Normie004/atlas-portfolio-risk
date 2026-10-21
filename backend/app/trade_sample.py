"""Synthetic ledger with deliberate issues for illustrating exception detection."""
TRADE_SAMPLE = {
    'opening_positions': [
        {'symbol': 'SHOP', 'currency':'CAD', 'quantity':'20'},
        {'symbol': 'AAPL', 'currency':'USD', 'quantity':'5'},
    ],
    'opening_cash': {'CAD':'10000', 'USD':'5000'},
    'trades': [
        {'trade_id':'T-1001', 'symbol':'SHOP', 'side':'BUY', 'quantity':'10', 'price':'95', 'currency':'CAD', 'fee':'5'},
        {'trade_id':'T-1002', 'symbol':'AAPL', 'side':'SELL', 'quantity':'2', 'price':'210', 'currency':'USD', 'fee':'1'},
        {'trade_id':'T-1003', 'symbol':'SHOP', 'side':'BUY', 'quantity':'2', 'price':'100', 'currency':'CAD', 'fee':'0'},
        # Duplicate trade ID should not count twice.
        {'trade_id':'T-1003', 'symbol':'SHOP', 'side':'BUY', 'quantity':'2', 'price':'100', 'currency':'CAD', 'fee':'0'},
        {'trade_id':'T-1004', 'symbol':'AAPL', 'side':'SELL', 'quantity':'20', 'price':'210', 'currency':'USD', 'fee':'1'},
        {'trade_id':'T-1005', 'symbol':'SHOP', 'side':'BUY', 'quantity':'100', 'price':'200', 'currency':'CAD', 'fee':'0'},
    ],
    'reported_positions': [
        {'symbol':'SHOP', 'currency':'CAD', 'quantity':'32'},
        {'symbol':'AAPL', 'currency':'USD', 'quantity':'4'},
    ],
    'reported_cash': {'CAD':'8845', 'USD':'5417'}
}
