import csv
import io
from decimal import Decimal, InvalidOperation
from fastapi import FastAPI, UploadFile, File, HTTPException
from fastapi.middleware.cors import CORSMiddleware
from fastapi.responses import PlainTextResponse
from pydantic import ValidationError
from .models import AnalyzeRequest
from .analytics import analyze
from .sample import SAMPLE
from .reconciliation import ReconcileRequest, reconcile
from .trade_sample import TRADE_SAMPLE
from .bank_fx import fetch_fx_history, FXUnavailable
from .fx_analytics import fx_translation_history

app = FastAPI(title='ATLAS Portfolio Analytics API', version='0.3.0')
app.add_middleware(
    CORSMiddleware,
    allow_origins=['http://localhost:5173','http://127.0.0.1:5173'],
    allow_credentials=False,
    allow_methods=['GET','POST'],
    allow_headers=['*'],
)

@app.get('/api/health')
def health():
    return {'status':'ok','project':'ATLAS','version':'0.3.0'}

@app.get('/api/sample')
def sample():
    return SAMPLE

@app.post('/api/analyze')
def analyze_portfolio(payload: AnalyzeRequest):
    try:
        return analyze(payload)
    except ValueError as exc:
        raise HTTPException(status_code=422, detail=str(exc)) from exc

@app.post('/api/portfolio/upload')
async def upload_portfolio(file: UploadFile = File(...)):
    if not file.filename or not file.filename.lower().endswith('.csv'):
        raise HTTPException(status_code=400, detail='Please upload a .csv portfolio file.')
    raw = await file.read(1024 * 1024 + 1)
    if len(raw) > 1024 * 1024:
        raise HTTPException(status_code=413, detail='CSV exceeds 1 MB.')
    try:
        decoded = raw.decode('utf-8-sig')
        reader = csv.DictReader(io.StringIO(decoded, newline=''))
        required = {'symbol','name','asset_class','currency','quantity','price'}
        if not reader.fieldnames or not required.issubset(reader.fieldnames):
            raise HTTPException(status_code=422, detail='Required columns: symbol,name,asset_class,currency,quantity,price')
        rows = [{key: (value or '').strip() for key,value in row.items() if key is not None} for row in reader]
        if len(rows) > 500:
            raise HTTPException(status_code=422, detail='Maximum 500 rows.')
        payload = AnalyzeRequest(holdings=rows, source_label='Uploaded CSV (not live prices)')
        return payload.model_dump(mode='json')
    except UnicodeDecodeError as exc:
        raise HTTPException(status_code=422, detail='CSV must be UTF-8 encoded.') from exc
    except (ValidationError, ValueError) as exc:
        raise HTTPException(status_code=422, detail=str(exc)) from exc

@app.get('/api/template', response_class=PlainTextResponse)
def csv_template():
    buffer=io.StringIO()
    writer=csv.writer(buffer)
    writer.writerow(['symbol','name','asset_class','currency','quantity','price'])
    writer.writerows([
       ['SHOP','Shopify demo','Equity','CAD',10,100],
       ['AAPL','Apple demo','Equity','USD',5,200],
       ['CASH','Cash demo','Cash','CAD',1000,1],
    ])
    return buffer.getvalue()


@app.get('/api/trades/sample')
def sample_trades():
    return TRADE_SAMPLE

@app.post('/api/trades/reconcile')
def reconcile_trades(payload: ReconcileRequest):
    try:
        return reconcile(payload)
    except ValueError as exc:
        raise HTTPException(status_code=422, detail=str(exc)) from exc


@app.get('/api/fx/usd-cad')
def latest_fx():
    """Latest official published Bank of Canada USD/CAD observation."""
    try:
        result = fetch_fx_history(days=5)
        # Return a small shape rather than history for this endpoint.
        return {k: value for k, value in result.items() if k != 'observations'}
    except FXUnavailable as exc:
        raise HTTPException(status_code=503, detail=str(exc)) from exc


@app.post('/api/fx/translation-history')
def translation_history(payload: AnalyzeRequest, days: int = 90):
    """FX-only historical translation of today's snapshot holdings and prices."""
    if not 2 <= days <= 365:
        raise HTTPException(status_code=422, detail='Days must be between 2 and 365.')
    try:
        fx_data = fetch_fx_history(days=days)
        return fx_translation_history(payload, fx_data)
    except FXUnavailable as exc:
        raise HTTPException(status_code=503, detail=str(exc)) from exc
    except ValueError as exc:
        raise HTTPException(status_code=422, detail=str(exc)) from exc
