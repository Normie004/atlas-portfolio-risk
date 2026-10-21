from decimal import Decimal
from fastapi.testclient import TestClient
from app.main import app
from app.models import AnalyzeRequest
from app.analytics import analyze

client=TestClient(app)

def test_health():
    assert client.get('/api/health').json()['status']=='ok'


def test_values_and_fx_exposure():
    p=AnalyzeRequest(holdings=[
        {'symbol':'CA','name':'CAD equity','asset_class':'Equity','currency':'CAD','quantity':'2','price':'100'},
        {'symbol':'US','name':'USD bond','asset_class':'Bond','currency':'USD','quantity':'3','price':'100'},
    ],usd_to_cad='1.50')
    out=analyze(p)
    assert out['total_value_cad']==650.0
    assert out['currency_exposures'][0]['name']=='USD'
    assert out['currency_exposures'][0]['value_cad']==450.0
    assert out['asset_exposures'][0]['name']=='Bond'
    assert sum(row['weight_pct'] for row in out['positions']) == 100.0


def test_fx_shock_only():
    p=AnalyzeRequest(holdings=[
        {'symbol':'CASHU','name':'USD cash','asset_class':'Cash','currency':'USD','quantity':'100','price':'1'},
    ],usd_to_cad='1.50',scenario={'equities_pct':0,'bonds_pct':0,'usd_fx_pct':-10})
    out=analyze(p)
    assert out['total_value_cad']==150.0
    assert out['scenario_value_cad']==135.0
    assert out['scenario_return_pct']==-10.0


def test_negative_quantities_rejected():
    data={'holdings':[{'symbol':'A','name':'A','asset_class':'Equity','currency':'CAD','quantity':-1,'price':100}]}
    assert client.post('/api/analyze',json=data).status_code==422


def test_zero_portfolio_rejected():
    data={'holdings':[{'symbol':'A','name':'A','asset_class':'Cash','currency':'CAD','quantity':0,'price':1}]}
    assert client.post('/api/analyze',json=data).status_code==422


def test_sample_api():
    sample=client.get('/api/sample').json()
    out=client.post('/api/analyze',json=sample)
    assert out.status_code==200
    assert out.json()['position_count']==7
    assert out.json()['total_value_cad']>100000


def test_csv_upload():
    content=b'symbol,name,asset_class,currency,quantity,price\nAAPL,Apple,Equity,USD,10,150\n'
    resp=client.post('/api/portfolio/upload',files={'file':('holdings.csv',content,'text/csv')})
    assert resp.status_code==200,resp.text
    assert resp.json()['holdings'][0]['symbol']=='AAPL'


def test_csv_missing_column():
    content=b'symbol,name,quantity,price\nAAPL,Apple,10,150\n'
    resp=client.post('/api/portfolio/upload',files={'file':('holdings.csv',content,'text/csv')})
    assert resp.status_code==422


def test_duplicate_ticker_distinct_lots_weights():
    p=AnalyzeRequest(holdings=[
        {'symbol':'AAPL','name':'Apple','asset_class':'Equity','currency':'USD','quantity':'10','price':'10'},
        {'symbol':'AAPL','name':'Apple','asset_class':'Equity','currency':'USD','quantity':'20','price':'10'},
    ],usd_to_cad='1')
    out=analyze(p)
    assert sorted(x['weight_pct'] for x in out['positions']) == [33.33,66.67]
