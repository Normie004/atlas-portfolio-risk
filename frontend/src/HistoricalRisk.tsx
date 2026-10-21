import { useEffect, useRef, useState } from 'react'

type Holding={symbol:string,name:string,asset_class:'Equity'|'Bond'|'ETF'|'Cash',currency:'CAD'|'USD',quantity:string,price:string}
type Portfolio={holdings:Holding[],usd_to_cad:string,source_label:string,scenario:{equities_pct:string,bonds_pct:string,usd_fx_pct:string}}
type PriceRow={date:string,symbol:string,currency:'CAD'|'USD',close:string}
type SourceData={source:string,prices:PriceRow[],source_url?:string,symbol_map?:Record<string,string>}
type HistoryResult={source:string,valuation_basis:string,fx_basis:string,first_date:string,last_date:string,observation_count:number,symbols:string[],start_value_cad:number,end_value_cad:number,price_only_change_pct:number,price_only_annualized_volatility_pct:number|null,price_only_max_drawdown_pct:number,observations:{date:string,value_cad:number,usd_to_cad:number}[],methodology:string}

const money=(n:number)=>new Intl.NumberFormat('en-CA',{style:'currency',currency:'CAD',maximumFractionDigits:0}).format(n)
const pct=(n:number)=>`${n.toFixed(2)}%`

async function api(path:string, opts?:RequestInit){const response=await fetch(path,opts);if(!response.ok){const error=await response.json().catch(()=>({detail:response.statusText}));throw new Error(typeof error.detail==='string'?error.detail:JSON.stringify(error.detail))}return response.json()}

export default function HistoricalRisk({portfolio}:{portfolio:Portfolio}){
 const [source,setSource]=useState<SourceData|null>(null)
 const [result,setResult]=useState<HistoryResult|null>(null)
 const [useOfficialFx,setUseOfficialFx]=useState(false)
 const [configured,setConfigured]=useState(false)
 const [busy,setBusy]=useState(false)
 const [error,setError]=useState('')
 const chooser=useRef<HTMLInputElement|null>(null)
 const requestId=useRef(0)

 useEffect(()=>{
  api('/api/history/market-status').then((v:{configured:boolean})=>setConfigured(v.configured)).catch(()=>setConfigured(false))
 },[])
 // Historical run belongs to its exact set of quantities/symbols, not a later CSV upload.
 useEffect(()=>{requestId.current++;setSource(null);setResult(null);setError('')},[portfolio.holdings])

 async function analyze(data:SourceData, official:boolean){
  const id=++requestId.current
  setBusy(true);setError('');setUseOfficialFx(official)
  try{
   const analysis=await api('/api/history/analyze',{
    method:'POST',headers:{'Content-Type':'application/json'},
    body:JSON.stringify({portfolio,prices:data.prices,source:data.source,use_official_fx:official})
   }) as HistoryResult
   if(id===requestId.current){setResult(analysis);setSource(data)}
  }catch(e){if(id===requestId.current){setSource(data);setResult(null);setError((e as Error).message)}}
  finally{if(id===requestId.current)setBusy(false)}
 }

 async function loadDemo(){
  setBusy(true);setError('')
  try{const history=await api('/api/history/sample') as SourceData;await analyze(history,false)}
  catch(e){setError((e as Error).message)}finally{setBusy(false)}
 }

 async function loadProvider(){
  setBusy(true);setError('')
  try{const history=await api('/api/history/alpha-vantage',{
   method:'POST',headers:{'Content-Type':'application/json'},body:JSON.stringify(portfolio)
  }) as SourceData;await analyze(history,true)}
  catch(e){setError((e as Error).message)}finally{setBusy(false)}
 }

 async function upload(file?:File){
  if(!file)return
  setBusy(true);setError('')
  try{
   const form=new FormData();form.append('file',file)
   const history=await api('/api/history/upload',{method:'POST',body:form}) as SourceData
   await analyze(history,false)
  }catch(e){setError((e as Error).message)}finally{setBusy(false)}
 }

 const points=result?.observations||[]
 const values=points.map(p=>p.value_cad)
 const min=values.length?Math.min(...values):0
 const max=values.length?Math.max(...values):1
 const gutter=Math.max((max-min)*0.15,max*.0007,1)
 const scale=(value:number)=>148-(value-(min-gutter))/(max-min+2*gutter)*120
 const polyline=points.map((p,i)=>`${(i/Math.max(points.length-1,1)*672+14).toFixed(1)},${scale(p.value_cad).toFixed(1)}`).join(' ')
 const isDemo=source?.source.toLowerCase().includes('synthetic')
 return <section id="price-history" className="panel historical-panel">
  <div className="section-head"><div><h3>Historical price & portfolio risk lab</h3><p className="small">Daily asset closing prices + CAD conversion, with fixed quantities. Not a trading backtest or total-return index.</p></div><span className="pill">HISTORICAL ANALYSIS / V0.4</span></div>
  <div className="historical-toolbar">
   <button className="primary" disabled={busy} onClick={()=>void loadDemo()}>{busy?'Working…':'Load synthetic historical demo'}</button>
   <button className="ghost compact" disabled={busy} onClick={()=>chooser.current?.click()}>↑ Import historical prices CSV</button>
   <input type="file" hidden ref={chooser} accept=".csv,text/csv" onChange={e=>{void upload(e.target.files?.[0]);e.target.value=''}}/>
   <button className="ghost compact" disabled={busy||!configured} onClick={()=>void loadProvider()}>↗ Fetch Alpha Vantage closes</button>
  </div>
  <div className="between hist-source-line"><span className="micro">Market-data integration: {configured?'API key configured':'No API key configured'} · <a href="https://www.alphavantage.co/support/#api-key" target="_blank" rel="noreferrer">Get personal key ↗</a></span>{source&&<span className="micro">{source.prices.length.toLocaleString()} dated prices loaded</span>}</div>
  {source&&<div className="history-options"><label><input type="checkbox" checked={useOfficialFx} disabled={busy} onChange={e=>void analyze(source,e.target.checked)}/> Use official historical USD/CAD (Bank of Canada)</label><span className="micro">Unchecked: fixed dashboard FX rate {portfolio.usd_to_cad}; checked: observed published rates only</span></div>}
  {error&&<div className="alert">{error}</div>}
  {result?<>
   <div className="historical-metrics">
    <div className="metric"><p className="eyebrow">END VALUE (CAD)</p><div className="metric-val">{money(result.end_value_cad)}</div><p className="small">Fixed holdings / latest available close</p></div>
    <div className="metric"><p className="eyebrow">PRICE-ONLY CHANGE</p><div className={'metric-val '+(result.price_only_change_pct<0?'negative':'positive')}>{pct(result.price_only_change_pct)}</div><p className="small">Between available first and last dates</p></div>
    <div className="metric"><p className="eyebrow">ANNUALIZED VOLATILITY</p><div className="metric-val">{result.price_only_annualized_volatility_pct===null?'—':pct(result.price_only_annualized_volatility_pct)}</div><p className="small">Sample daily CAD price changes × √252</p></div>
    <div className="metric"><p className="eyebrow">MAXIMUM DRAWDOWN</p><div className="metric-val negative">{pct(result.price_only_max_drawdown_pct)}</div><p className="small">Within the observed window</p></div>
   </div>
   <div className="fx-chart"><div className="between"><span className="micro">{isDemo?'SYNTHETIC closing prices':'Historical closing prices'} · {result.observation_count} shared observations</span><span className="mono">Start {money(result.start_value_cad)}</span></div><svg viewBox="0 0 700 175" role="img" aria-label="CAD fixed-quantity portfolio mark-to-market values through price observations"><line x1="14" y1="148" x2="686" y2="148" stroke="#30435d"/><line x1="14" y1="87" x2="686" y2="87" stroke="#25354a" strokeDasharray="4 5"/><polyline points={polyline} fill="none" stroke="#85b9ff" strokeWidth="2.5" strokeLinejoin="round" strokeLinecap="round"/></svg><div className="between micro"><span>{result.first_date}</span><span>{result.last_date}</span></div></div>
   <div className="history-source"><strong>{result.source}</strong> · {result.symbols.join(', ')}<p className="micro">FX basis: {result.fx_basis}</p>{source?.source_url&&<a href={source.source_url} target="_blank" rel="noreferrer">Price provider documentation ↗</a>}</div>
   <p className="micro fx-methodology">{result.methodology}</p>
  </>:<p className="small hist-help">Start with the synthetic demo to check the calculation engine. To analyze genuine market data, upload licensed historical close data (CSV: <code>date,symbol,currency,close</code>) or configure Alpha Vantage in your backend. The portfolio symbols and quote currencies must match exactly. No real market data is silently substituted.</p>}
 </section>
}
