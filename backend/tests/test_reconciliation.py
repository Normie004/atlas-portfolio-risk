from fastapi.testclient import TestClient
from app.main import app
from app.reconciliation import ReconcileRequest, reconcile
from app.trade_sample import TRADE_SAMPLE

client=TestClient(app)


def test_demo_has_both_trading_and_reporting_exceptions():
    result=reconcile(ReconcileRequest.model_validate(TRADE_SAMPLE))
    assert result['trades_received']==6
    assert result['trades_applied']==3
    assert result['trades_rejected']==3
    assert result['break_count']==2
    assert {e['code'] for e in result['trade_exceptions']} == {
        'DUPLICATE_TRADE_ID', 'INSUFFICIENT_POSITION', 'INSUFFICIENT_CASH'
    }
    assert result['expected_cash']=={'CAD':'8845', 'USD':'5419'}
    assert {x['symbol']:x['quantity'] for x in result['expected_positions']} == {'AAPL':'3', 'SHOP':'32'}


def test_reconcile_api():
    assert client.get('/api/trades/sample').status_code==200
    r=client.post('/api/trades/reconcile',json=TRADE_SAMPLE)
    assert r.status_code==200
    assert r.json()['break_count']==2


def test_no_breaks_with_correct_report():
    sample={**TRADE_SAMPLE,'reported_cash':{'CAD':'8845','USD':'5419'},
            'reported_positions':[{'symbol':'SHOP','currency':'CAD','quantity':'32'},
                                  {'symbol':'AAPL','currency':'USD','quantity':'3'}]}
    result=reconcile(ReconcileRequest.model_validate(sample))
    assert result['break_count']==0
    assert result['trades_rejected']==3  # validation issues are independent of breaks


def test_oversell_is_not_applied():
    sample={**TRADE_SAMPLE,'trades':[{'trade_id':'A','symbol':'AAPL','side':'SELL','quantity':6,
                                     'price':100,'currency':'USD'}]}
    result=reconcile(ReconcileRequest.model_validate(sample))
    assert result['trades_applied']==0
    assert any(e['code']=='INSUFFICIENT_POSITION' for e in result['trade_exceptions'])


def test_nonnegative_cash_validation():
    sample={**TRADE_SAMPLE,'opening_cash':{'CAD':'-1','USD':'0'}}
    r=client.post('/api/trades/reconcile',json=sample)
    assert r.status_code==422


def test_duplicate_opening_position_rejected():
    sample={**TRADE_SAMPLE,'opening_positions':[
        {'symbol':'SHOP','currency':'CAD','quantity':'2'},
        {'symbol':'SHOP','currency':'CAD','quantity':'3'}]}
    r=client.post('/api/trades/reconcile',json=sample)
    assert r.status_code==422


def test_fee_adjusts_cash():
    sample={
        'opening_positions':[{'symbol':'AAA','currency':'CAD','quantity':1}],
        'opening_cash':{'CAD':'100', 'USD':'0'},
        'trades':[{'trade_id':'X','symbol':'AAA','side':'BUY','quantity':2,'price':10,'currency':'CAD','fee':0.75}],
        'reported_positions':[{'symbol':'AAA','currency':'CAD','quantity':3}],
        'reported_cash':{'CAD':'79.25','USD':'0'}
    }
    out=reconcile(ReconcileRequest.model_validate(sample))
    assert out['expected_cash']['CAD']=='79.25'
    assert out['break_count']==0
    assert out['trades_applied']==1
