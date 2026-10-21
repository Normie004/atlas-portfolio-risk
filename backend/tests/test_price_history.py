from copy import deepcopy
from decimal import Decimal

import pytest
from fastapi.testclient import TestClient

from app import main
from app.models import AnalyzeRequest
from app.price_history import PriceHistoryRequest, PriceRow, compute_price_history, parse_price_csv, HistoricalDataError
from app.sample_prices import sample_price_rows
from app.alpha_vantage import parse_daily_closes, MarketDataUnavailable, fetch_daily_prices

client = TestClient(main.app)


def portfolio(currency='CAD'):
    return AnalyzeRequest.model_validate({
        'holdings':[
            {'symbol':'TEST','name':'Test equity','asset_class':'Equity','currency':currency,'quantity':'2','price':'15'},
            {'symbol':'CASH','name':'Cash','asset_class':'Cash','currency':'CAD','quantity':'100','price':'1'},
        ],
        'usd_to_cad':'1.25'
    })


def rows(currency='CAD', prices=('10','11','12','13','14','15')):
    return [PriceRow(date=f'2026-10-{10+i:02}',symbol='TEST',currency=currency,close=price) for i,price in enumerate(prices)]


def test_static_holdings_mark_to_market_not_return_index():
    request=PriceHistoryRequest(portfolio=portfolio(),prices=rows(),source='Unit fixture',use_official_fx=False)
    result=compute_price_history(request)
    assert result['start_value_cad']==120.0
    assert result['end_value_cad']==130.0
    assert result['price_only_change_pct']==pytest.approx(8.33,abs=.02)
    assert result['observation_count']==6
    assert result['price_only_max_drawdown_pct']==0
    assert result['price_only_annualized_volatility_pct']>0


def test_usd_fx_applied_to_positions_with_prior_only():
    request=PriceHistoryRequest(portfolio=portfolio('USD'),prices=rows('USD'),source='Unit',use_official_fx=True)
    published=[{'date':'2026-10-09','usd_to_cad':'1.20'}, {'date':'2026-10-12','usd_to_cad':'1.40'}, {'date':'2026-10-15','usd_to_cad':'1.50'}]
    out=compute_price_history(request,published)
    assert out['observations'][0]['usd_to_cad']==1.2
    assert out['observations'][2]['usd_to_cad']==1.4
    assert out['observations'][-1]['value_cad']==145  # 2*15*1.5 + 100 CAD


def test_fx_requires_authoritative_history():
    with pytest.raises(HistoricalDataError,match='Published USD/CAD'):
        compute_price_history(PriceHistoryRequest(portfolio=portfolio('USD'),prices=rows('USD'),source='U',use_official_fx=True))


def test_no_lookahead_fx_stale_days_rejected():
    request=PriceHistoryRequest(portfolio=portfolio('USD'),prices=rows('USD'),source='U',use_official_fx=True)
    with pytest.raises(HistoricalDataError,match='Fewer than five'):
        compute_price_history(request,[{'date':'2026-10-01','usd_to_cad':'1.4'}])


def test_mismatched_quote_currency_is_error():
    request=PriceHistoryRequest(portfolio=portfolio('CAD'),prices=rows('USD'),source='U',use_official_fx=False)
    with pytest.raises(HistoricalDataError,match='price currency'):
        compute_price_history(request)


def test_duplicate_price_day_rejected():
    request=PriceHistoryRequest(portfolio=portfolio(),prices=rows()+[rows()[0]],source='U',use_official_fx=False)
    with pytest.raises(HistoricalDataError,match='Duplicate price'):
        compute_price_history(request)


def test_only_common_dates_accepted():
    d=portfolio().model_dump(mode='json')
    d['holdings'].insert(0,{'symbol':'OTHER','name':'Other','asset_class':'Equity','currency':'CAD','quantity':'1','price':'2'})
    price_rows=rows()+[PriceRow(date=f'2026-10-{10+i:02}',symbol='OTHER',currency='CAD',close='10') for i in range(1,6)]
    out=compute_price_history(PriceHistoryRequest(portfolio=AnalyzeRequest.model_validate(d),prices=price_rows,source='U',use_official_fx=False))
    assert out['first_date']=='2026-10-11'
    assert out['observation_count']==5


def test_flat_prices_zero_vol_and_drawdown():
    r=compute_price_history(PriceHistoryRequest(portfolio=portfolio(),prices=rows(prices=['10']*6),source='U',use_official_fx=False))
    assert r['price_only_annualized_volatility_pct']==0
    assert r['price_only_max_drawdown_pct']==0


@pytest.mark.parametrize('data,message',[
    (b'symbol,close\nTEST,100', 'Expected CSV columns'),
    (b'date,symbol,currency,close\n2026-10-10,TEST,CAD,-2', 'Invalid historical price row'),
    (b'date,symbol,currency,close\n2026-10-10,TEST,CAD,4\n2026-10-10,TEST,CAD,5','Duplicate historical price'),
    (b'date,symbol,currency,close\n2026-10-10,TEST,USD,NaN','Invalid historical price row'),
])
def test_bad_csv_rejected(data,message):
    with pytest.raises(HistoricalDataError,match=message):parse_price_csv(data)


def test_price_sample_is_reproducible_and_complete():
    data=sample_price_rows()
    assert data==sample_price_rows()
    assert data['observation_dates']==65
    assert len(data['prices'])==65*6
    assert all(x['close']!='0' for x in data['prices'])


def test_historical_sample_endpoints_return_synthetic_and_correctly_compute():
    sample=client.get('/api/sample').json()
    historical=client.get('/api/history/sample')
    assert historical.status_code==200
    response=client.post('/api/history/analyze',json={'portfolio':sample,'prices':historical.json()['prices'],'source':historical.json()['source'],'use_official_fx':False})
    assert response.status_code==200,response.text
    data=response.json()
    assert data['observation_count']==65
    assert data['end_value_cad']>0
    assert data['source'].startswith('Deterministic synthetic')


def test_historical_upload_requires_currency():
    import io
    ok=client.post('/api/history/upload',files={'file':('prices.csv',io.BytesIO(b'date,symbol,currency,close\n2026-10-10,TEST,CAD,20'), 'text/csv')})
    assert ok.status_code==200
    bad=client.post('/api/history/upload',files={'file':('prices.csv',io.BytesIO(b'date,symbol,close\n2026-10-10,TEST,20'), 'text/csv')})
    assert bad.status_code==422


def test_provider_parse_handles_raw_closes_and_rate_limits():
    sample={'Time Series (Daily)':{f'2026-10-{10+i:02}':{'4. close':str(100+i)} for i in range(6)}}
    out=parse_daily_closes(sample,'TEST','USD')
    assert out[0]['close']=='100'
    with pytest.raises(MarketDataUnavailable,match='Alpha Vantage returned'):
        parse_daily_closes({'Note':'limit exceeded'},'TEST','USD')


def test_missing_key_does_not_trigger_external_fetch(monkeypatch):
    monkeypatch.delenv('ALPHAVANTAGE_API_KEY',raising=False)
    with pytest.raises(MarketDataUnavailable,match='not configured'):
        fetch_daily_prices(portfolio().holdings)
