from .models import AnalyzeRequest

# Everything in this sample is SYNTHETIC, including the USD/CAD FX rate.
# These are NOT current prices or investment recommendations.
SAMPLE = {
    'source_label': 'Synthetic sample portfolio',
    'usd_to_cad': '1.37',
    'holdings': [
        {'symbol':'RY',   'name':'Royal Bank of Canada (demo)', 'asset_class':'Equity', 'currency':'CAD', 'quantity':'180', 'price':'160'},
        {'symbol':'SHOP', 'name':'Shopify (demo)',             'asset_class':'Equity', 'currency':'CAD', 'quantity':'120', 'price':'145'},
        {'symbol':'AAPL', 'name':'Apple (demo)',               'asset_class':'Equity', 'currency':'USD', 'quantity':'80',  'price':'225'},
        {'symbol':'MSFT', 'name':'Microsoft (demo)',           'asset_class':'Equity', 'currency':'USD', 'quantity':'55',  'price':'450'},
        {'symbol':'XBB',  'name':'Canadian bond ETF (demo)',   'asset_class':'Bond',   'currency':'CAD', 'quantity':'500', 'price':'30'},
        {'symbol':'BND',  'name':'US bond ETF (demo)',         'asset_class':'Bond',   'currency':'USD', 'quantity':'400', 'price':'73'},
        {'symbol':'CASH', 'name':'CAD cash (demo)',             'asset_class':'Cash',   'currency':'CAD', 'quantity':'12500', 'price':'1'},
    ],
    'scenario': {'equities_pct':'-5', 'bonds_pct':'-2', 'usd_fx_pct':'-3'}
}
