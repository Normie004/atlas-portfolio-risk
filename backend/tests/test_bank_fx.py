from copy import deepcopy
from decimal import Decimal

import httpx
import pytest
from fastapi.testclient import TestClient

from app import bank_fx, main
from app.fx_analytics import fx_translation_history
from app.models import AnalyzeRequest

client = TestClient(main.app)


def fake_valet():
    return {'observations': [
        {'d':'2026-10-16','FXUSDCAD':{'v':'1.3500'}},
        {'d':'2026-10-19','FXUSDCAD':{'v':'1.4000'}},
        {'d':'2026-10-20','FXUSDCAD':{'v':'1.4500'}},
    ]}


def test_parse_sort_and_skip_empty_nontrading_day():
    body = deepcopy(fake_valet())
    body['observations'] = [body['observations'][2], {'d':'2026-10-18'}, *body['observations'][:2]]
    observations = bank_fx.parse_observations(body)
    assert [x['date'] for x in observations] == ['2026-10-16','2026-10-19','2026-10-20']
    assert observations[-1]['usd_to_cad'] == '1.4500'


@pytest.mark.parametrize('bad', [
    {'observations': []},
    {'observations': [{'d':'2026-10-20','FXUSDCAD':{'v':'-1'}}]},
    {'observations': [{'d':'2026-10-20','FXUSDCAD':{'v':'nan'}}]},
    {'observations': [{'d':'not-a-date','FXUSDCAD':{'v':'1.35'}}]},
    {'observations': [{'d':'2026-10-20','FXUSDCAD':{'v':'1.30'}}, {'d':'2026-10-20','FXUSDCAD':{'v':'1.35'}}]},
    {'wrong':'shape'},
    [],
])
def test_invalid_fx_payloads_are_rejected(bad):
    with pytest.raises(bank_fx.FXUnavailable):
        bank_fx.parse_observations(bad)


def test_static_holdings_fx_valuation():
    req=AnalyzeRequest(holdings=[
      {'symbol':'CAD','name':'Canadian cash','asset_class':'Cash','currency':'CAD','quantity':'100','price':'1'},
      {'symbol':'USD','name':'US cash','asset_class':'Cash','currency':'USD','quantity':'100','price':'1'},
    ])
    data={'observations':bank_fx.parse_observations(fake_valet()),
          'source':'Bank of Canada Valet API','source_url':'https://www.bankofcanada.ca/valet-api-how-to/',
          'observation_date':'2026-10-20','retrieved_at_utc':'2026-10-21T19:00:00Z',
          'cache_status':'miss','latest_usd_to_cad':'1.4500'}
    out=fx_translation_history(req,data)
    assert [v['value_cad'] for v in out['observations']]==[235.0,240.0,245.0]
    assert out['latest_value_cad']==245.0
    assert out['fx_only_change_pct']==4.26
    assert out['usd_exposure_pct']==59.18
    assert out['fx_only_max_drawdown_pct']==0
    assert out['fx_only_annualized_volatility_pct'] is not None


def test_cad_only_is_flat_across_fx():
    req=AnalyzeRequest(holdings=[{'symbol':'C','name':'CAD','asset_class':'Cash','currency':'CAD','quantity':'100','price':'1'}])
    data={'observations':bank_fx.parse_observations(fake_valet()),
          'source':'Bank of Canada Valet API','source_url':'source','observation_date':'2026-10-20',
          'retrieved_at_utc':'utc','cache_status':'hit','latest_usd_to_cad':'1.4500'}
    out=fx_translation_history(req,data)
    assert out['fx_only_change_pct']==0
    assert out['fx_only_annualized_volatility_pct']==0
    assert out['usd_exposure_pct']==0


def test_cache_avoids_repeated_provider_calls(monkeypatch):
    bank_fx._cache.clear()
    calls=[]
    class FakeClient:
        def __init__(self, **kwargs): pass
        def __enter__(self): return self
        def __exit__(self, *args): pass
        def get(self,url,params):
            calls.append((url,params))
            return httpx.Response(200,json=fake_valet(),request=httpx.Request('GET',url))
    monkeypatch.setattr(bank_fx.httpx,'Client',FakeClient)
    a=bank_fx.fetch_fx_history(30)
    b=bank_fx.fetch_fx_history(30)
    assert a['cache_status']=='miss' and b['cache_status']=='hit'
    assert len(calls)==1
    assert calls[0][1]=={'recent':30}
    bank_fx._cache.clear()


def test_endpoints_and_provider_failure(monkeypatch):
    sample=client.get('/api/sample').json()
    rates=bank_fx.parse_observations(fake_valet())
    def fake_fetch(days=90):
        return {'observations':rates,'source':'Bank of Canada Valet API','source_url':'source',
                'observation_date':'2026-10-20','retrieved_at_utc':'utc',
                'cache_status':'hit','latest_usd_to_cad':'1.4500'}
    monkeypatch.setattr(main,'fetch_fx_history',fake_fetch)
    response=client.post('/api/fx/translation-history?days=90',json=sample)
    assert response.status_code==200,response.text
    assert response.json()['observation_date']=='2026-10-20'
    assert len(response.json()['observations'])==3
    latest=client.get('/api/fx/usd-cad')
    assert latest.status_code==200
    assert 'observations' not in latest.json()
    assert client.post('/api/fx/translation-history?days=366',json=sample).status_code==422
    def broken(days=90): raise bank_fx.FXUnavailable('Rate feed is unavailable')
    monkeypatch.setattr(main,'fetch_fx_history',broken)
    assert client.post('/api/fx/translation-history?days=90',json=sample).status_code==503
    assert client.get('/api/fx/usd-cad').status_code==503
