import { useEffect, useRef, useState } from 'react'
import HistoricalRisk from './HistoricalRisk'

type Holding={symbol:string,name:string,asset_class:'Equity'|'Bond'|'ETF'|'Cash',currency:'CAD'|'USD',quantity:string,price:string}
type Request={holdings:Holding[],usd_to_cad:string,source_label:string,scenario:{equities_pct:string,bonds_pct:string,usd_fx_pct:string}}
type Exposure={name:string,weight_pct:number,value_cad:number}
type Position=Holding & {value_cad:number,weight_pct:number,scenario_pnl_cad:number}
type Result={total_value_cad:number,scenario_value_cad:number,scenario_pnl_cad:number,scenario_return_pct:number,largest_position_pct:number,position_count:number,asset_exposures:Exposure[],currency_exposures:Exposure[],positions:Position[],data_status:string,assumptions:string[]}
type LedgerPosition={symbol:string,currency:'CAD'|'USD',quantity:string}
type LedgerTrade={trade_id:string,symbol:string,side:'BUY'|'SELL',quantity:string,price:string,currency:'CAD'|'USD',fee:string}
type TradeRequest={opening_positions:LedgerPosition[],opening_cash:Record<'CAD'|'USD',string>,trades:LedgerTrade[],reported_positions:LedgerPosition[],reported_cash:Record<'CAD'|'USD',string>}
type FxHistoryResult={source:string,source_url:string,observation_date:string,latest_usd_to_cad:number,latest_value_cad:number,fx_only_change_pct:number,fx_only_annualized_volatility_pct:number|null,fx_only_max_drawdown_pct:number,usd_exposure_pct:number,methodology:string,cache_status:string,observations:{date:string,usd_to_cad:number,value_cad:number}[]}
type TradeResult={trades_received:number,trades_applied:number,trades_rejected:number,break_count:number,expected_positions:LedgerPosition[],expected_cash:Record<'CAD'|'USD',string>,trade_exceptions:{code:string,trade_id:string,detail:string}[],reconciliation_breaks:{type:string,key:string,currency:string,expected:string,reported:string,difference:string}[],audit_log:{trade_id:string,symbol:string,side:string,status:string,reason:string|null}[]}

const money=(n:number)=>new Intl.NumberFormat('en-CA',{style:'currency',currency:'CAD',maximumFractionDigits:0}).format(n)
const pct=(n:number)=>`${n.toFixed(1)}%`
const palette:Record<string,string>={Equity:'#6aa5ff',ETF:'#b39bff',Bond:'#59d6ae',Cash:'#ffca7e',CAD:'#6aa5ff',USD:'#b39bff'}

async function api(path:string,opts?:RequestInit){const resp=await fetch(path,opts);if(!resp.ok){const body=await resp.json().catch(()=>({detail:resp.statusText}));throw new Error(typeof body.detail==='string'?body.detail:JSON.stringify(body.detail))}return resp.json()}

function Metric({label,value,foot,tone}:{label:string,value:string,foot:string,tone?:string}){return <div className="metric"><p className="eyebrow">{label}</p><div className={'metric-val '+(tone||'')}>{value}</div><p className="small">{foot}</p></div>}

function ExposureBars({title,data}:{title:string,data:Exposure[]}){return <section className="panel"><div className="section-head"><h3>{title}</h3><span className="micro">CAD market value</span></div><div className="bar-stack">{data.map(e=><div key={e.name} className="bar-item"><div className="between"><span className="bar-name"><i style={{background:palette[e.name]||'#98a8ba'}}/>{e.name}</span><span className="mono">{pct(e.weight_pct)}</span></div><div className="track"><div className="fill" style={{width:`${Math.max(0,e.weight_pct)}%`,background:palette[e.name]||'#98a8ba'}}/></div><span className="micro">{money(e.value_cad)}</span></div>)}</div></section>}


function ReconciliationLab(){
 const [request,setRequest]=useState<TradeRequest|null>(null)
 const [result,setResult]=useState<TradeResult|null>(null)
 const [busy,setBusy]=useState(false)
 const [error,setError]=useState('')
 async function run(payload:TradeRequest){setBusy(true);try{const value=await api('/api/trades/reconcile',{method:'POST',headers:{'Content-Type':'application/json'},body:JSON.stringify(payload)}) as TradeResult;setResult(value);setError('')}catch(e){setError((e as Error).message)}finally{setBusy(false)}}
 useEffect(()=>{api('/api/trades/sample').then((sample:TradeRequest)=>{setRequest(sample);return run(sample)}).catch(e=>setError((e as Error).message))},[])
 const editPosition=(i:number,v:string)=>setRequest(prev=>prev?{...prev,reported_positions:prev.reported_positions.map((x,j)=>j===i?{...x,quantity:v}:x)}:null)
 const editCash=(ccy:'CAD'|'USD',v:string)=>setRequest(prev=>prev?{...prev,reported_cash:{...prev.reported_cash,[ccy]:v}}:null)
 const match=()=>{if(!request||!result)return;const fixed={...request,reported_cash:{...result.expected_cash},reported_positions:result.expected_positions};setRequest(fixed);void run(fixed)}
 const reset=async()=>{try{const original=await api('/api/trades/sample') as TradeRequest;setRequest(original);await run(original)}catch(e){setError((e as Error).message)}}
 return <section id="reconciliation" className="panel reconcile-panel">
 <div className="section-head"><div><h3>Trade blotter & reconciliation</h3><p className="small">Validate synthetic orders, recalculate cash and positions, and identify ledger breaks.</p></div><span className="pill">PAPER TRADES / V0.2</span></div>
 <div className="notice recon-notice"><span className="status-led amber"/><strong>SIMULATION ONLY</strong><span>No brokerage connection; no real orders, settlement, or live market prices.</span></div>
 {error&&<div className="alert">{error}</div>}
 {result&&<div className="recon-stats"><Metric label="TRADES APPLIED" value={String(result.trades_applied)} foot={`${result.trades_received} received`}/><Metric label="INVALID TRADES" value={String(result.trades_rejected)} foot="Rejected before ledger updates" tone={result.trades_rejected>0?'negative':''}/><Metric label="RECONCILIATION BREAKS" value={String(result.break_count)} foot="Reported vs calculated balances" tone={result.break_count>0?'negative':'positive'}/></div>}
 <div className="recon-grid"><div><h4>Simulated trade blotter</h4><div className="table-scroll"><table><thead><tr><th>ID</th><th>TRADE</th><th>QUANTITY</th><th>PRICE</th><th>STATUS</th></tr></thead><tbody>{request?.trades.map((trade,i)=>{const event=result?.audit_log[i];return <tr key={i}><td className="mono">{trade.trade_id}</td><td><strong>{trade.side} {trade.symbol}</strong><span className="table-sub">{trade.currency}</span></td><td className="mono">{trade.quantity}</td><td className="mono">{trade.price}</td><td><span className={event?.status==='APPLIED'?'positive':'negative'}>{event?.status||'—'}</span></td></tr>})}</tbody></table></div></div>
 <div><h4>External reported balances <span className="micro">(editable)</span></h4><div className="recon-edit"><div className="recon-edit-head">Positions</div>{request?.reported_positions.map((p,i)=><label key={`${p.symbol}-${p.currency}`}><span>{p.symbol} <small>{p.currency}</small></span><input type="number" step="any" min="0" value={p.quantity} onChange={e=>editPosition(i,e.target.value)}/></label>)}<div className="recon-edit-head">Cash</div>{(['CAD','USD'] as const).map(ccy=><label key={ccy}><span>{ccy} cash</span><input type="number" step="0.01" min="0" value={request?.reported_cash[ccy]||'0'} onChange={e=>editCash(ccy,e.target.value)}/></label>)}</div><div className="recon-buttons"><button className="primary" disabled={!request||busy} onClick={()=>request&&void run(request)}>{busy?'Checking…':'Run reconciliation'}</button><button className="ghost compact" disabled={!result||!request||busy} onClick={match}>Match calculated</button><button className="ghost compact" disabled={busy} onClick={()=>void reset()}>Reset demo</button></div></div></div>
 {result&&<div className="recon-results"><div><h4>Reconciliation breaks <span className="micro">({result.break_count})</span></h4>{result.reconciliation_breaks.length?result.reconciliation_breaks.map((b,i)=><div className="recon-exception" key={i}><strong>{b.type} / {b.key}</strong><span>Expected {b.expected} · reported {b.reported} · difference {b.difference}</span></div>):<p className="positive small">All reported balances match the calculated ledger.</p>}</div><div><h4>Trade validation exceptions <span className="micro">({result.trade_exceptions.length})</span></h4>{result.trade_exceptions.length?result.trade_exceptions.map((e,i)=><div className="recon-exception" key={i}><strong>{e.code.replaceAll('_',' ')} · {e.trade_id}</strong><span>{e.detail}</span></div>):<p className="positive small">No trade validation exceptions.</p>}</div></div>}
 <p className="micro recon-footer">Reported balances are deliberately different in the demo. Select “Match calculated” to clear reconciliation breaks; rejected trade exceptions stay visible until their trade instructions are corrected.</p>
 </section>
}

function FxHistory({input,onRate}:{input:Request,onRate:(rate:number,date:string)=>void}){
 const [result,setResult]=useState<FxHistoryResult|null>(null)
 const [busy,setBusy]=useState(false)
 const [error,setError]=useState('')
 const [days,setDays]=useState(90)
 // History belongs to one portfolio snapshot. Clear when CSV/holdings change.
 useEffect(()=>{setResult(null);setError('')},[input.holdings])
 async function load(){
  setBusy(true);setError('')
  try{
   const value=await api(`/api/fx/translation-history?days=${days}`,{method:'POST',headers:{'Content-Type':'application/json'},body:JSON.stringify(input)}) as FxHistoryResult
   setResult(value)
  }catch(e){setError((e as Error).message)}finally{setBusy(false)}
 }
 const points=result?.observations||[]
 const values=points.map(p=>p.value_cad)
 const lo=values.length?Math.min(...values):0
 const hi=values.length?Math.max(...values):1
 const margin=Math.max((hi-lo)*.15,hi*.0005,1)
 const scaleY=(v:number)=>148-(v-(lo-margin))/(hi-lo+2*margin)*120
 const plot=points.map((p,i)=>`${(i/Math.max(points.length-1,1)*672+14).toFixed(1)},${scaleY(p.value_cad).toFixed(1)}`).join(' ')
 return <section id="fx-history" className="panel fx-history-panel">
  <div className="section-head"><div><h3>Bank of Canada FX monitor</h3><p className="small">Historical currency translation of fixed portfolio holdings — not historical stock returns.</p></div><span className="pill">PUBLISHED FX / V0.3</span></div>
  <div className="fx-history-actions"><label>Observation window <select value={days} onChange={e=>setDays(Number(e.target.value))}><option value={30}>30 business observations</option><option value={90}>90 business observations</option><option value={180}>180 business observations</option></select></label><button className="primary" disabled={busy} onClick={()=>void load()}>{busy?'Fetching official rates…':'Load official FX history'}</button></div>
  {error&&<div className="alert">{error} Your editable demo exchange rate is unchanged.</div>}
  {result?<>
   <div className="fx-history-metrics"><Metric label="LATEST PUBLISHED USD/CAD" value={result.latest_usd_to_cad.toFixed(4)} foot={`Bank of Canada · ${result.observation_date}`}/><Metric label="FX-ONLY PORTFOLIO CHANGE" value={pct(result.fx_only_change_pct)} foot="Static quantities and native prices" tone={result.fx_only_change_pct<0?'negative':'positive'}/><Metric label="FX-ONLY VOLATILITY" value={result.fx_only_annualized_volatility_pct===null?'—':pct(result.fx_only_annualized_volatility_pct)} foot="Annualized sample daily FX-translation returns"/><Metric label="FX-ONLY MAX DRAWDOWN" value={pct(result.fx_only_max_drawdown_pct)} foot="Based on the FX-translation series"/></div>
   <div className="fx-chart"><div className="between"><span className="micro">Constant native prices · variable published USD/CAD · CAD</span><span className="mono">Latest value {money(result.latest_value_cad)}</span></div><svg viewBox="0 0 700 175" role="img" aria-label="Historical CAD portfolio valuation with frozen native prices and changing USD CAD exchange rate"><line x1="14" y1="148" x2="686" y2="148" stroke="#30435d"/><line x1="14" y1="87" x2="686" y2="87" stroke="#25354a" strokeDasharray="4 5"/><polyline points={plot} fill="none" stroke="#73dbc5" strokeWidth="2.5" strokeLinejoin="round" strokeLinecap="round"/></svg><div className="between micro"><span>{points[0]?.date}</span><span>{points[points.length-1]?.date}</span></div></div>
   <div className="fx-history-actions"><span className="micro">Published rate: {result.observation_date} · {points.length} observations · <a href={result.source_url} target="_blank" rel="noopener noreferrer">Bank of Canada methodology ↗</a></span><button className="ghost compact" onClick={()=>onRate(result.latest_usd_to_cad,result.observation_date)}>Use published FX rate in overview</button></div>
   <p className="micro fx-methodology">{result.methodology} The source publishes on business days and may not yet include today's data. This is not an executable FX quote.</p>
  </>:<p className="small fx-intro">Select a window and fetch official USD/CAD observations. ATLAS never substitutes a demo value when the Bank of Canada API is unavailable.</p>}
 </section>
}

export default function App(){
 const [input,setInput]=useState<Request|null>(null)
 const [data,setData]=useState<Result|null>(null)
 const [error,setError]=useState('')
 const [working,setWorking]=useState(false)
 const [uploaded,setUploaded]=useState(false)
 const [officialRateDate,setOfficialRateDate]=useState<string|null>(null)
 const picker=useRef<HTMLInputElement|null>(null)
 const lastRequest=useRef(0)
 useEffect(()=>{api('/api/sample').then((sample:Request)=>setInput(sample)).catch(e=>setError('Cannot connect to backend. Start FastAPI first. '+e.message))},[])
 useEffect(()=>{
  if(!input)return
  const id=++lastRequest.current
  const t=setTimeout(()=>{setWorking(true);api('/api/analyze',{method:'POST',headers:{'Content-Type':'application/json'},body:JSON.stringify(input)})
   .then((r:Result)=>{if(id===lastRequest.current){setData(r);setError('')}})
   .catch(e=>{if(id===lastRequest.current)setError(e.message)})
   .finally(()=>{if(id===lastRequest.current)setWorking(false)})},160)
  return ()=>clearTimeout(t)
 },[input])
 const setScenario=(name:keyof Request['scenario'],v:number)=>setInput(o=>o?{...o,scenario:{...o.scenario,[name]:String(v)}}:o)
 async function onFile(file?:File){if(!file)return;setWorking(true);try{const form=new FormData();form.append('file',file);const parsed=await api('/api/portfolio/upload',{method:'POST',body:form}) as Request;setInput(o=>({...parsed,usd_to_cad:o?.usd_to_cad||parsed.usd_to_cad,scenario:o?.scenario||parsed.scenario}));setUploaded(true);setError('')}catch(e){setError((e as Error).message)}finally{setWorking(false)}}
 const reset=()=>{api('/api/sample').then((s:Request)=>{setInput(s);setUploaded(false);setOfficialRateDate(null);setError('')})}
 const applyOfficialRate=(rate:number,date:string)=>{setInput(o=>o?{...o,usd_to_cad:String(rate)}:o);setOfficialRateDate(date)}
 return <div className="app-shell">
  <aside className="sidebar"><div className="logo"><div className="logo-mark">A</div><div><b>ATLAS</b><span>PORTFOLIO SYSTEMS</span></div></div>
   <div className="nav-caption">WORKSPACE</div><a className="nav-item active" href="#overview"><span className="nav-dot"/> Portfolio overview</a><a className="nav-item" href="#exposure">◇ &nbsp; Exposure analysis</a><a className="nav-item" href="#positions">≡ &nbsp; Position ledger</a><a className="nav-item" href="#reconciliation">⇄ &nbsp; Trade reconciliation</a><a className="nav-item" href="#fx-history">↗ &nbsp; Official FX monitor</a><a className="nav-item" href="#price-history">⌁ &nbsp; Historical risk</a><a className="nav-item" href="#methodology">◈ &nbsp; Methodology</a>
   <div className="sidebar-bottom"><div className="terminal-label"><span className="status-led"/> LOCAL DEMO</div><div className="micro">Synthetic demo; optional genuine historical closes and published FX.</div><div className="version">ATLAS / VERSION 0.4</div></div>
  </aside>
  <main id="overview" className="content"><header className="header"><div><p className="overline">PORTFOLIO INTELLIGENCE / OVERVIEW</p><h1>Risk overview<span className="accent">.</span></h1><p className="subtitle">Portfolio valuation, asset exposure and hypothetical stress analysis.</p></div><div className="header-actions"><button className="ghost" onClick={reset}>↺ Reset demo</button><button className="primary" onClick={()=>picker.current?.click()}>↑ Upload CSV</button><input ref={picker} hidden type="file" accept=".csv,text/csv" onChange={e=>{onFile(e.target.files?.[0]);e.target.value=''}}/></div></header>
  <div className="notice"><span className="status-led amber"/><strong>EDUCATIONAL DEMO</strong><span>Overview still uses synthetic or user-supplied spot prices. Historical lab handles separate dated closes and optional official FX; neither implies live trading. Not investment advice.</span></div>
  {error&&<div className="alert"><b>Something needs attention:</b> {error}</div>}
  {input&&<div className="utility"><div><span className="overline">DATA SOURCE</span><div className="source">{uploaded?'Uploaded CSV':'Synthetic sample portfolio'} <span className="pill">{input.holdings.length} positions</span></div></div><div className="fx-control"><label htmlFor="fx">USD → CAD reference FX rate {officialRateDate?<span className="positive">· BoC {officialRateDate}</span>:<span>· demo/manual</span>}</label><input id="fx" type="number" min="0.01" max="10" step="0.01" value={input.usd_to_cad} onChange={e=>{setInput({...input,usd_to_cad:e.target.value});setOfficialRateDate(null)}}/></div></div>}
  {data?<>
   <div className="metrics"><Metric label="TOTAL MARKET VALUE" value={money(data.total_value_cad)} foot="Portfolio marked in CAD"/><Metric label="HYPOTHETICAL SCENARIO P&L" value={(data.scenario_pnl_cad>=0?'+':'')+money(data.scenario_pnl_cad)} foot={`${pct(data.scenario_return_pct)} under selected shocks`} tone={data.scenario_pnl_cad<0?'negative':'positive'}/><Metric label="TOP POSITION WEIGHT" value={pct(data.largest_position_pct)} foot="Largest single holding"/><Metric label="POSITIONS" value={String(data.position_count).padStart(2,'0')} foot="Across CAD and USD"/></div>
   <div id="exposure" className="grid2"><ExposureBars title="Asset allocation" data={data.asset_exposures}/><ExposureBars title="Currency exposure" data={data.currency_exposures}/></div>
   <section className="panel scenario-panel"><div className="section-head"><div><h3>Stress scenario lab</h3><p className="small">Change one assumption and see the hypothetical impact across the portfolio.</p></div><span className="pill">SCENARIO ENGINE / V1</span></div>
   <div className="scenario-grid">{([{key:'equities_pct',title:'Equity & ETF shock',min:-40,max:20},{key:'bonds_pct',title:'Bond shock',min:-20,max:20},{key:'usd_fx_pct',title:'USD/CAD shock',min:-20,max:20}] as const).map(s=><div className="slider-group" key={s.key}><div className="between"><label htmlFor={s.key}>{s.title}</label><b className="mono">{Number(input?.scenario[s.key]||0)>0?'+':''}{input?.scenario[s.key]}%</b></div><input id={s.key} type="range" min={s.min} max={s.max} value={input?.scenario[s.key]||0} onChange={e=>setScenario(s.key,Number(e.target.value))}/><div className="range-ends"><span>{s.min}%</span><span>{s.max}%</span></div></div>)}</div>
   <div className="scenario-outcome"><div><span className="overline">SCENARIO PORTFOLIO VALUE</span><strong>{money(data.scenario_value_cad)}</strong></div><span className={'scenario-change '+(data.scenario_pnl_cad<0?'negative':'positive')}>{data.scenario_pnl_cad>=0?'+':''}{money(data.scenario_pnl_cad)} / {pct(data.scenario_return_pct)}</span></div></section>
   <section id="positions" className="panel table-panel"><div className="section-head"><div><h3>Position ledger</h3><p className="small">Valuation derived from supplied quantity × price × currency conversion.</p></div><button className="ghost compact" onClick={()=>window.open('/api/template','_blank')}>↓ Sample CSV format</button></div><div className="table-scroll"><table><thead><tr><th>INSTRUMENT</th><th>CLASS</th><th>CCY</th><th>QUANTITY</th><th>PRICE</th><th>VALUE (CAD)</th><th>WEIGHT</th><th>SCENARIO P&L</th></tr></thead><tbody>{data.positions.map((p,i)=><tr key={`${p.symbol}-${i}`}><td><strong>{p.symbol}</strong><span className="table-sub">{p.name}</span></td><td>{p.asset_class}</td><td>{p.currency}</td><td className="mono">{Number(p.quantity).toLocaleString('en-CA')}</td><td className="mono">{Number(p.price).toLocaleString('en-CA',{minimumFractionDigits:2,maximumFractionDigits:2})}</td><td className="mono">{money(p.value_cad)}</td><td className="mono">{pct(p.weight_pct)}</td><td className={'mono '+(p.scenario_pnl_cad<0?'negative':'positive')}>{p.scenario_pnl_cad>=0?'+':''}{money(p.scenario_pnl_cad)}</td></tr>)}</tbody></table></div></section>
   <ReconciliationLab/>
   {input&&<FxHistory input={input} onRate={applyOfficialRate}/>}
   {input&&<HistoricalRisk portfolio={input}/>}
   <section id="methodology" className="bottom-grid"><div className="panel mini"><h3>Methodology notes</h3><ul>{data.assumptions.map(a=><li key={a}>{a}</li>)}</ul></div><div className="panel mini"><h3>Next releases</h3><div className="roadmap"><span>02</span><div><b>Official FX translation history</b><small>Bank of Canada observations (v0.3)</small></div></div><div className="roadmap"><span>03</span><div><b>Historical asset pricing</b><small>Fixed-holdings price-only returns and risk (v0.4)</small></div></div><div className="roadmap"><span>04</span><div><b>Research assistant</b><small>Auditable natural-language insights</small></div></div></div></section>
   <footer>ATLAS / LOCAL DEVELOPMENT BUILD <span>{working?'RECALCULATING…':'CALCULATIONS READY'}</span></footer>
  </>:<div className="loading">Starting risk engine…</div>}
 </main></div>
}
