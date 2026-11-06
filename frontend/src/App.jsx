import { useEffect, useMemo, useRef, useState } from 'react';

import { Area, AreaChart, Bar, BarChart, CartesianGrid, ResponsiveContainer, Tooltip, XAxis, YAxis } from 'recharts';

import './App.css';



const DEFAULT_IP = import.meta.env.VITE_ESP32_IP || '10.46.89.4';



const BACKEND_BASE = import.meta.env.VITE_BACKEND_URL || '';



const NAV = [

  { id: 'dashboard', icon: '▦', label: 'Dashboard' },

  { id: 'history', icon: '◷', label: 'History Log' },

  { id: 'spectrometry', icon: '∿', label: 'Spectrometry' },

  { id: 'photodiode', icon: '♡', label: 'Photodiode' },

  { id: 'trials', icon: '⚕', label: 'Research Notes' },

  { id: 'settings', icon: '⚙', label: 'System Settings' },

];



function fmt(v, digits = 0) {

  if (v === undefined || v === null || v === '' || !Number.isFinite(Number(v))) return '—';

  return Number(v).toLocaleString(undefined, { maximumFractionDigits: digits, minimumFractionDigits: digits });

}



// MongoDB timestamps are UTC. Some API responses omit the trailing Z, so

// explicitly treat timezone-less ISO timestamps as UTC before displaying in IST.

function fmtDateTime(value) {

  if (!value) return '—';

  const raw = String(value);

  const hasTimezone = /(?:Z|[+-]\d{2}:?\d{2})$/i.test(raw);

  const date = new Date(hasTimezone ? raw : `${raw}Z`);

  if (Number.isNaN(date.getTime())) return '—';

  return date.toLocaleString('en-IN', {

    timeZone: 'Asia/Kolkata',

    day: '2-digit', month: '2-digit', year: 'numeric',

    hour: '2-digit', minute: '2-digit', second: '2-digit', hour12: true,

  });

}

function StatCard({ label, value, unit, sub, accent = 'red' }) {

  return <article className={`stat-card accent-${accent}`}><div className="stat-head"><span>{label}</span><i /></div><div className="stat-value">{value}<small>{unit}</small></div><p>{sub}</p></article>;

}

function Pill({ children, kind = 'neutral' }) { return <span className={`pill ${kind}`}><i />{children}</span>; }



export default function App() {

  const [ip, setIp] = useState(() => localStorage.getItem('glucosense-esp32-ip') || DEFAULT_IP);

  const [ipDraft, setIpDraft] = useState(ip);

  const [page, setPage] = useState('dashboard');

  const [data, setData] = useState(null);

  const [connection, setConnection] = useState('connecting');

  const [error, setError] = useState('');

  const [updated, setUpdated] = useState(null);

  const [history, setHistory] = useState([]);

  const [saved, setSaved] = useState(() => { try { return JSON.parse(localStorage.getItem('glucosense-saved-readings') || '[]'); } catch { return []; } });

  const [modal, setModal] = useState('');

  const [notice, setNotice] = useState('');

  const [baseline, setBaseline] = useState(() => { try { return JSON.parse(localStorage.getItem('glucosense-baseline') || 'null'); } catch { return null; } });

  const [backendHealth, setBackendHealth] = useState(null);

  const [backendModel, setBackendModel] = useState(null);

  const [backendHistory, setBackendHistory] = useState([]);

  const [backendError, setBackendError] = useState('');
  const [prediction, setPrediction] = useState(null);
  const [predictionError, setPredictionError] = useState('');
  const [predictionLoading, setPredictionLoading] = useState(false);
  const [predictionUpdated, setPredictionUpdated] = useState(null);
  const lastPredictionAt = useRef(0);



  useEffect(() => {

    let alive = true;

    const poll = async () => {

      try {

        const res = await fetch(`http://${ip}/api/data`, { cache: 'no-store' });

        if (!res.ok) throw new Error(`HTTP ${res.status}`);

        const json = await res.json();

        if (!alive) return;

        setData(json); setConnection('connected'); setError(''); setUpdated(new Date());

        setHistory(prev => [...prev.slice(-59), sampleFrom(json)]);

      } catch (e) {

        if (!alive) return;

        setConnection('disconnected'); setError(e.message || 'API unavailable');

      }

    };

    poll(); const timer = setInterval(poll, 1000);

    return () => { alive = false; clearInterval(timer); };

  }, [ip]);



  useEffect(() => {

    let alive = true;

    const refreshBackend = async () => {

      try {

        const [healthRes, modelRes, readingsRes] = await Promise.all([

          fetch(`${BACKEND_BASE}/health`, { cache: 'no-store' }),

          fetch(`${BACKEND_BASE}/api/model/status`, { cache: 'no-store' }),

          fetch(`${BACKEND_BASE}/api/readings?limit=20`, { cache: 'no-store' })

        ]);

        if (!healthRes.ok) throw new Error(`Health HTTP ${healthRes.status}`);

        const health = await healthRes.json();

        const model = modelRes.ok ? await modelRes.json() : null;

        const readings = readingsRes.ok ? await readingsRes.json() : [];

        if (!alive) return;

        setBackendHealth(health);

        setBackendModel(model);

        setBackendHistory(Array.isArray(readings) ? readings : []);

        setBackendError(health.database_connected ? '' : 'Backend is running, but MongoDB is not connected.');

      } catch (e) {

        if (!alive) return;

        setBackendHealth(null);

        setBackendModel(null);

        setBackendError(e.message || 'Backend API unavailable');

      }

    };

    refreshBackend();

    const timer = setInterval(refreshBackend, 10000);

    return () => { alive = false; clearInterval(timer); };

  }, []);



  const channels = Array.isArray(data?.channels) ? data.channels : [];

  // Call the synthetic demo prediction endpoint at most once every five seconds.
  useEffect(() => {
    if (!data) return;
    const now = Date.now();
    if (now - lastPredictionAt.current < 5000) return;
    lastPredictionAt.current = now;

    const payload = {
      device_id: data.device_id || `esp32-${ip.replaceAll('.', '-')}`,
      timestamp: new Date().toISOString(),
      channels: Array.isArray(data.channels) ? data.channels.map(Number) : [],
      led_850_raw: data.led_850_raw ?? data.red ?? 0,
      led_940_raw: data.led_940_raw ?? data.ir ?? 0,
      red: data.red ?? 0,
      ir: data.ir ?? 0,
      pulse_bpm: data.pulse_bpm ?? data.pulseBpm ?? null,
      object_temp_c: data.objectTempC ?? data.object_temp_c ?? null,
      ambient_temp_c: data.ambientTempC ?? data.ambient_temp_c ?? null,
      skin_temp_c: data.skin_temp_c ?? data.skinTempC ?? null,
      adc_raw: data.adcRaw ?? data.adc_raw ?? [],
      adc_volts: data.adcVolts ?? data.adc_volts ?? [],
      signal_quality: ['unassessed', 'poor', 'fair', 'good'].includes(data.signal_quality)
        ? data.signal_quality : 'unassessed',
      reference_glucose_mg_dl: null,
      session_id: data.session_id || `dashboard-${new Date().toISOString().slice(0, 10)}`,
      participant_code: 'dashboard-demo',
      metadata: { capture_source: 'live-dashboard-demo' }
    };

    setPredictionLoading(true);
    fetch(`${BACKEND_BASE}/api/predict`, {
      method: 'POST',
      headers: { 'Content-Type': 'application/json' },
      body: JSON.stringify(payload)
    })
      .then(async response => {
        const result = await response.json().catch(() => ({}));
        if (!response.ok) {
          const detail = Array.isArray(result.detail)
            ? result.detail.map(item => {
                const field = Array.isArray(item.loc) ? item.loc.slice(1).join('.') : 'input';
                return `${field}: ${item.msg || 'invalid value'}`;
              }).join(' · ')
            : typeof result.detail === 'string'
              ? result.detail
              : `Prediction HTTP ${response.status}`;
          throw new Error(detail);
        }
        setPrediction(result);
        setPredictionError('');
        setPredictionUpdated(new Date());
      })
      .catch(error => {
        setPredictionError(error.message || 'Prediction API unavailable');
      })
      .finally(() => {
        setPredictionLoading(false);
      });

  }, [data, ip]);

  const samples = useMemo(() => history.map((s, i) => ({ ...s, label: s.time, index: i })), [history]);

  const latest = history.at(-1) || null;

  const sensorStatus = [

    ['AS7343 spectral array', data?.as7343Ready ?? (channels.length > 0)],

    ['MAX30102 photodiode', data?.max30102Ready ?? (data?.red != null || data?.ir != null)],

    ['MLX90614 temperature', data?.mlx90614Ready ?? (data?.objectTempC != null && Number(data.objectTempC) !== 0)],

    ['I²C ADC / ADS1115', data?.ads1115Ready ?? (data?.adcRaw != null || data?.adcVolts != null)],

  ];



  function sampleFrom(d) {

    return {

      time: new Date().toLocaleTimeString(), timestamp: new Date().toISOString(),

      nir: Number(d.nir ?? d.channels?.[3] ?? 0), vis: Number(d.vis ?? d.channels?.[4] ?? 0),

      red: Number(d.red ?? 0), ir: Number(d.ir ?? 0), objectTempC: d.objectTempC == null ? null : Number(d.objectTempC),

      ambientTempC: d.ambientTempC == null ? null : Number(d.ambientTempC), adcRaw: d.adcRaw ?? [], adcVolts: d.adcVolts ?? [], channels: d.channels ?? []

    };

  }

  async function saveReading() {
    if (!data) {
      setNotice('No live data available yet. Connect the ESP32 first.');
      return;
    }

    const snapshot = sampleFrom(data);
    const objectTemp = data.objectTempC ?? data.object_temp_c ?? null;
    const ambientTemp = data.ambientTempC ?? data.ambient_temp_c ?? null;

    const payload = {
      device_id: data.device_id || `esp32-${ip.replaceAll('.', '-')}`,
      timestamp: snapshot.timestamp,
      channels: Array.isArray(data.channels) && data.channels.length
        ? data.channels.map(Number)
        : [snapshot.nir || 0, snapshot.vis || 0],
      led_850_raw: data.led_850_raw ?? data.red ?? null,
      led_940_raw: data.led_940_raw ?? data.ir ?? null,
      pulse_bpm: data.pulse_bpm ?? data.pulseBpm ?? null,

      // Keep MLX90614 object and ambient temperatures as separate measurements.
      // Do not automatically label object temperature as skin temperature.
      object_temp_c: objectTemp == null ? null : Number(objectTemp),
      ambient_temp_c: ambientTemp == null ? null : Number(ambientTemp),
      skin_temp_c: data.skin_temp_c ?? data.skinTempC ?? null,

      signal_quality: ['unassessed', 'poor', 'fair', 'good'].includes(data.signal_quality)
        ? data.signal_quality
        : 'unassessed',
      session_id: data.session_id || `dashboard-${new Date().toISOString().slice(0, 10)}`,
      metadata: {
        nir: snapshot.nir,
        vis: snapshot.vis,
        red: snapshot.red,
        ir: snapshot.ir,
        objectTempC: snapshot.objectTempC,
        ambientTempC: snapshot.ambientTempC,
        adcRaw: snapshot.adcRaw,
        adcVolts: snapshot.adcVolts,
        capture_source: 'dashboard'
      }
    };

    try {
      const response = await fetch(`${BACKEND_BASE}/api/readings/dashboard`, {
        method: 'POST',
        headers: { 'Content-Type': 'application/json' },
        body: JSON.stringify(payload)
      });

      const result = await response.json().catch(() => ({}));
      if (!response.ok) {
        throw new Error(result.detail || `Save failed (HTTP ${response.status})`);
      }

      const refreshed = await fetch(`${BACKEND_BASE}/api/readings?limit=100`, {
        cache: 'no-store'
      });

      if (refreshed.ok) {
        const rows = await refreshed.json();
        setBackendHistory(Array.isArray(rows) ? rows : []);
      }

      setBackendError('');
      setNotice('Reading saved to MongoDB Atlas.');
    } catch (e) {
      setBackendError(e.message || 'Could not save reading to backend.');
      setNotice(`MongoDB save failed: ${e.message || 'Backend unavailable'}`);
    }

    setTimeout(() => setNotice(''), 4500);
  }

  function exportCsv() {

    const rows = backendHistory.length ? backendHistory.map(r => ({

      timestamp: r.timestamp, device_id: r.device_id, nir: r.metadata?.nir ?? r.channels?.[3] ?? '',

      vis: r.metadata?.vis ?? r.channels?.[4] ?? '', red: r.metadata?.red ?? r.led_850_raw ?? '',

            ir: r.metadata?.ir ?? r.led_940_raw ?? '',

objectTempC: r.object_temp_c ?? r.metadata?.objectTempC ?? '',

ambientTempC: r.ambient_temp_c ?? r.metadata?.ambientTempC ?? '',

          channels: r.channels ?? [], source: r.source ?? '',

})) : saved;

    if (!rows.length) { setNotice('No backend readings available to export yet.'); return; }

    const header = ['timestamp','device_id','nir','vis','red','ir','objectTempC','ambientTempC','channels','source'];

    const csv = [header.join(','), ...rows.map(r => header.map(k => {

      const v = r[k]; return `"${(Array.isArray(v) ? v.join('|') : v ?? '').toString().replaceAll('"','""')}"`;

    }).join(','))].join('\r\n');

    const url = URL.createObjectURL(new Blob([csv], { type: 'text/csv;charset=utf-8;' }));

    const a = document.createElement('a'); a.href = url; a.download = 'glucosense-readings.csv'; a.click(); URL.revokeObjectURL(url);

    setNotice('CSV export started.'); setTimeout(() => setNotice(''), 3000);

  }

  function connectIp(e) {
    e.preventDefault();
    const clean = ipDraft.trim().replace(/^https?:\/\//i, '').replace(/\/.*$/, '');

    if (!clean) {
      setNotice('Enter a valid ESP32 IP address.');
      return;
    }

    localStorage.setItem('glucosense-esp32-ip', clean);
    setIp(clean);
    setConnection('connecting');
    setError('');
    setPage('dashboard');
    setModal('');
    setNotice('ESP32 target updated. Testing connection…');
    setTimeout(() => setNotice(''), 3000);
  }

  function calibrateBaseline() {

    if (!data) { setNotice('Cannot capture a baseline without live sensor data.'); return; }

    const b = { capturedAt: new Date().toISOString(), channels: data.channels ?? [], nir: data.nir ?? data.channels?.[3] ?? null, vis: data.vis ?? data.channels?.[4] ?? null, red: data.red ?? null, ir: data.ir ?? null };

    setBaseline(b); localStorage.setItem('glucosense-baseline', JSON.stringify(b)); setModal(''); setNotice('Signal baseline saved locally. This is not glucose calibration.'); setTimeout(() => setNotice(''), 4000);

  }

  function clearSaved() { setSaved([]); localStorage.removeItem('glucosense-saved-readings'); setNotice('Saved reading history cleared.'); setTimeout(() => setNotice(''), 3000); }

  const pageTitle = NAV.find(n => n.id === page)?.label || 'Dashboard';



  return <div className="layout">

    <aside className="sidebar">

      <button className="brand" onClick={() => setPage('dashboard')} aria-label="Go to dashboard"><span className="brand-icon">G<sup>+</sup></span><span><b>GlucoSense<span className="brand-dot">.</span></b><small>NON-INVASIVE RESEARCH</small></span></button>

      <div className="nav-caption">WORKSPACE</div>

      <nav>{NAV.slice(0,5).map(n => <button key={n.id} className={`nav-link ${page===n.id?'active':''}`} onClick={() => setPage(n.id)}><span className="nav-icon">{n.icon}</span>{n.label}</button>)}</nav>

      <div className="sidebar-spacer" />

      <button className={`nav-link settings-link ${page==='settings'?'active':''}`} onClick={() => setPage('settings')}><span className="nav-icon">⚙</span>System Settings</button>

      <div className="device-box"><div className="device-row"><Pill kind={connection==='connected'?'online':connection==='connecting'?'warning':'offline'}>{connection==='connected'?'Online':connection==='connecting'?'Connecting':'Offline'}</Pill><span className="device-label">ESP32 DEVICE</span></div><b>{ip}</b><small>{connection==='connected'?'Connected to sensor API':'Waiting for API response'}</small></div>

      <div className="sidebar-foot">EXPERIMENTAL DATA ONLY</div>

    </aside>



    <main className="main">

      <header className="topbar"><div><div className="kicker">GLUCOSENSE / RESEARCH CONSOLE</div><h1>{page==='dashboard'?'Edge-AI Signal Monitor':pageTitle}</h1><p>{page==='dashboard'?'Live sensor telemetry and optical signal diagnostics':page==='history'?'Saved readings collected from your device':page==='spectrometry'?'Multispectral raw channel measurements':page==='photodiode'?'MAX30102 red and infrared signal stream':page==='trials'?'Research notes and experimental safeguards':'Device connection and dashboard preferences'}</p></div><div className="top-actions"><div className="hardware-pill"><span className={`pulse ${connection==='connected'?'on':''}`}/><span>ESP32</span><b>{connection==='connected'?'ONLINE':'NOT CONNECTED'}</b></div><button className="btn btn-ghost" onClick={() => setModal('baseline')}>◎ Capture baseline</button><button className="btn btn-primary" onClick={saveReading}>▣ Save reading</button></div></header>

      {notice && <div className="toast" role="status">{notice}<button onClick={() => setNotice('')} aria-label="Dismiss">×</button></div>}

      {error && <div className="error-banner"><b>Sensor API unreachable.</b> {error}. Confirm ESP32 and laptop are on the same Wi-Fi/hotspot and open <code>http://{ip}/api/data</code> to test the endpoint.</div>}



      {page==='dashboard' && <>

        <section className="hero-grid">

          <article className="glucose-panel"><div className="panel-title"><div><span className="section-tag">MODEL OUTPUT</span><h2>Glucose estimation</h2></div><Pill kind="warning">NOT VALIDATED</Pill></div><div className="no-glucose"><span className="drop-icon">◈</span><div>
              {prediction?.prediction_available && prediction?.synthetic_demo ? <>
                <strong>{fmt(prediction.estimated_glucose_mg_dl, 1)} mg/dL</strong>
                <p>Synthetic demo output only · Model {prediction.model_version || 'demo'}</p>
              </> : <>
                <strong>{predictionLoading ? 'Generating demo output…' : 'Demo output unavailable'}</strong>
                <p>{predictionError || 'Waiting for live ESP32 data and the synthetic demo model.'}</p>
              </>}
            </div></div><div className="panel-divider"/><div className="model-metrics"><div><span>Signal baseline</span><b>{baseline?'Captured':'Not captured'}</b></div><div><span>Live samples</span><b>{history.length}</b></div><div><span>Prediction updated</span><b>{predictionUpdated ? predictionUpdated.toLocaleTimeString() : '—'}</b></div></div><div className="warning-note">{prediction?.synthetic_demo ? (prediction.notice || 'Synthetic demo output only. Not a glucose measurement and not for clinical decisions.') : 'Raw optical readings cannot be converted to mg/dL without a validated model and reference measurements.'}</div></article>

          <article className="chart-card ppg-card"><div className="chart-header"><div><h2>Continuous photodiode PPG</h2><p>MAX30102 · raw red and IR counts</p></div><span className="live-label"><i/>LIVE</span></div><div className="chart-wrap large-chart"><ResponsiveContainer width="100%" height="100%"><AreaChart data={samples}><defs><linearGradient id="redArea" x1="0" y1="0" x2="0" y2="1"><stop offset="0%" stopColor="#f43f5e" stopOpacity=".28"/><stop offset="100%" stopColor="#f43f5e" stopOpacity="0"/></linearGradient></defs><CartesianGrid stroke="#28252d" strokeDasharray="3 4"/><XAxis dataKey="label" tick={{fill:'#8d8996',fontSize:10}} minTickGap={40}/><YAxis tick={{fill:'#8d8996',fontSize:10}}/><Tooltip contentStyle={{background:'#171418',border:'1px solid #49303a',borderRadius:9,color:'#fff'}}/><Area type="monotone" dataKey="red" name="Red" stroke="#fb7185" fill="url(#redArea)" isAnimationActive={false}/><Area type="monotone" dataKey="ir" name="Infrared" stroke="#e11d48" fill="transparent" isAnimationActive={false}/></AreaChart></ResponsiveContainer></div><div className="chart-legend"><span><i className="key-red"/> Red</span><span><i className="key-pink"/> Infrared</span></div></article>

        </section>

        <section className="section"><div className="section-heading"><div><span className="section-tag">LIVE TELEMETRY</span><h2>Sensor readings</h2></div><span className="last-updated">{updated?`Updated ${updated.toLocaleTimeString()}`:'Waiting for readings'} <i className="live-dot"/></span></div><div className="stats-grid">

          <StatCard label="AS7343 · NIR (mapped)" value={fmt(data?.nir ?? channels[3])} unit="counts" sub="Raw spectral channel; mapping needs verification."/>

          <StatCard label="AS7343 · VIS (mapped)" value={fmt(data?.vis ?? channels[4])} unit="counts" sub="Raw spectral channel; mapping needs verification." accent="amber"/>

          <StatCard label="MAX30102 · Red" value={fmt(data?.red)} unit="counts" sub="Raw red optical signal." accent="pink"/>

          <StatCard label="MAX30102 · Infrared" value={fmt(data?.ir)} unit="counts" sub="Raw IR optical signal." accent="purple"/>

          <StatCard label="MLX90614 · Object" value={data?.mlx90614Ready===false?'—':fmt(data?.objectTempC,2)} unit="°C" sub={data?.mlx90614Ready===false?'Sensor not detected.':'Object temperature; verify sensor status.'} accent="amber"/>

          <StatCard label="MLX90614 · Ambient" value={data?.mlx90614Ready===false?'—':fmt(data?.ambientTempC,2)} unit="°C" sub={data?.mlx90614Ready===false?'Sensor not detected.':'Sensor ambient temperature.'} accent="pink"/>

          <StatCard label="ADS1115 · A0" value={fmt(data?.adcVolts?.[0],3)} unit="V" sub={`Raw ADC: ${fmt(data?.adcRaw?.[0])}`}/>

          <StatCard label="ADS1115 · A1" value={fmt(data?.adcVolts?.[1],3)} unit="V" sub={`Raw ADC: ${fmt(data?.adcRaw?.[1])}`} accent="purple"/>

        </div></section>

        <section className="section"><div className="section-heading"><div><span className="section-tag">SPECTRAL ANALYSIS</span><h2>AS7343 channel profile</h2></div><span className="subtle">{channels.length} raw channel values</span></div><div className="chart-card spectrum-card"><div className="chart-wrap spectrum-chart"><ResponsiveContainer width="100%" height="100%"><BarChart data={channels.map((v,i)=>({name:`CH ${i+1}`,value:Number(v)||0}))}><CartesianGrid stroke="#28252d" strokeDasharray="3 4" vertical={false}/><XAxis dataKey="name" tick={{fill:'#96909b',fontSize:10}}/><YAxis tick={{fill:'#96909b',fontSize:10}}/><Tooltip contentStyle={{background:'#171418',border:'1px solid #49303a',borderRadius:9,color:'#fff'}}/><Bar dataKey="value" fill="#e11d48" radius={[4,4,0,0]}/></BarChart></ResponsiveContainer></div></div></section>

        <section className="section"><div className="section-heading"><div><span className="section-tag">HARDWARE HEALTH</span><h2>Module status</h2></div><button className="text-button" onClick={()=>setPage('settings')}>Connection settings ↗</button></div><div className="module-grid">{sensorStatus.map(([name,ready])=><div className="module-item" key={name}><span className={`module-dot ${ready?'ok':'bad'}`}/><span>{name}</span><b className={ready?'good-text':'bad-text'}>{ready?'Detected':'Not detected'}</b></div>)}</div></section>

      </>}



      {page==='history' && <section className="section page-section"><div className="section-heading"><div><span className="section-tag">MONGODB ATLAS</span><h2>History log</h2><p>{backendHealth?.database_connected ? `${backendHistory.length} readings loaded from the backend database.` : 'Waiting for a database connection.'} {backendError && <span className="bad-text">{backendError}</span>}</p></div><div className="inline-actions"><button className="btn btn-ghost" onClick={async()=>{try{const r=await fetch(`${BACKEND_BASE}/api/readings?limit=100`,{cache:'no-store'});if(!r.ok)throw new Error(`HTTP ${r.status}`);const rows=await r.json();setBackendHistory(Array.isArray(rows)?rows:[]);setBackendError('');setNotice('History refreshed from MongoDB.');}catch(e){setBackendError(e.message);setNotice(`Refresh failed: ${e.message}`);}}}>↻ Refresh history</button><button className="btn btn-ghost" onClick={exportCsv}>↓ Export CSV</button><button className="btn btn-danger-ghost" onClick={clearSaved}>Clear local history</button></div></div><div className="table-card"><table><thead><tr><th>Saved at / timestamp</th><th>NIR</th><th>VIS</th><th>Red</th><th>IR</th><th>Object °C</th><th>Ambient °C</th></tr></thead><tbody>{backendHistory.length?backendHistory.map((r,i)=><tr key={r._id||`${r.timestamp}-${i}`}><td>{fmtDateTime(r.timestamp)}</td><td>{fmt(r.metadata?.nir ?? r.channels?.[3])}</td><td>{fmt(r.metadata?.vis ?? r.channels?.[4])}</td><td>{fmt(r.metadata?.red ?? r.led_850_raw)}</td><td>{fmt(r.metadata?.ir ?? r.led_940_raw)}</td><td>{fmt(r.object_temp_c ?? r.metadata?.objectTempC,2)}</td><td>{fmt(r.ambient_temp_c ?? r.metadata?.ambientTempC,2)}</td></tr>):<tr><td colSpan="7" className="empty-cell">No readings in MongoDB yet. Connect the ESP32 and click “Save reading”.</td></tr>}</tbody></table></div></section>}



      {page==='spectrometry' && <section className="section page-section"><div className="section-heading"><div><span className="section-tag">AS7343 MULTISPECTRAL SENSOR</span><h2>Spectral channels</h2><p>Raw sensor counts received from the ESP32 API. Channel labels are generic until verified against the library's channel order.</p></div><button className="btn btn-ghost" onClick={saveReading}>▣ Save snapshot</button></div><div className="channel-grid">{channels.length?channels.map((v,i)=><div className="channel-card" key={i}><span>CHANNEL {i+1}</span><strong>{fmt(v)}</strong><div className="meter"><i style={{width:`${Math.min(100,Math.max(1,(Number(v)||0)/65535*100))}%`}}/></div></div>):<div className="empty-state">Waiting for AS7343 channel values…</div>}</div><div className="chart-card standalone-chart"><div className="chart-header"><div><h2>Channel comparison</h2><p>Current raw count snapshot</p></div></div><div className="chart-wrap spectrum-chart"><ResponsiveContainer width="100%" height="100%"><BarChart data={channels.map((v,i)=>({name:`CH ${i+1}`,value:Number(v)||0}))}><CartesianGrid stroke="#28252d" strokeDasharray="3 4" vertical={false}/><XAxis dataKey="name" tick={{fill:'#96909b',fontSize:10}}/><YAxis tick={{fill:'#96909b',fontSize:10}}/><Tooltip contentStyle={{background:'#171418',border:'1px solid #49303a',borderRadius:9,color:'#fff'}}/><Bar dataKey="value" fill="#e11d48" radius={[4,4,0,0]}/></BarChart></ResponsiveContainer></div></div></section>}



      {page==='photodiode' && <section className="section page-section"><div className="section-heading"><div><span className="section-tag">MAX30102</span><h2>Photodiode signal</h2><p>Raw red/infrared counts; not a glucose reading.</p></div><button className="btn btn-primary" onClick={saveReading}>▣ Save snapshot</button></div><div className="stats-grid two-col"><StatCard label="Red channel" value={fmt(data?.red)} unit="counts" sub="Raw red LED detector count." accent="pink"/><StatCard label="Infrared channel" value={fmt(data?.ir)} unit="counts" sub="Raw IR LED detector count." accent="purple"/></div><div className="chart-card standalone-chart"><div className="chart-header"><div><h2>Live optical stream</h2><p>Last 60 samples</p></div><span className="live-label"><i/>LIVE</span></div><div className="chart-wrap large-chart"><ResponsiveContainer width="100%" height="100%"><AreaChart data={samples}><CartesianGrid stroke="#28252d" strokeDasharray="3 4"/><XAxis dataKey="label" tick={{fill:'#8d8996',fontSize:10}} minTickGap={40}/><YAxis tick={{fill:'#8d8996',fontSize:10}}/><Tooltip contentStyle={{background:'#171418',border:'1px solid #49303a',borderRadius:9,color:'#fff'}}/><Area type="monotone" dataKey="red" name="Red" stroke="#fb7185" fill="#fb71851c" isAnimationActive={false}/><Area type="monotone" dataKey="ir" name="Infrared" stroke="#e11d48" fill="transparent" isAnimationActive={false}/></AreaChart></ResponsiveContainer></div></div></section>}



      {page==='trials' && <section className="section page-section"><div className="section-heading"><div><span className="section-tag">RESEARCH SAFEGUARDS</span><h2>Research notes</h2><p>Prototype status and interpretation limits.</p></div></div><div className="notes-grid"><article className="note-card"><span className="note-symbol">!</span><h3>No clinical glucose output</h3><p>The dashboard may display a synthetic demo model output for software integration testing. It is not a real glucose estimate or measurement. Raw optical readings alone cannot establish blood glucose.</p></article><article className="note-card"><span className="note-symbol">⌁</span><h3>Reference measurements required</h3><p>Any future model needs a documented protocol, synchronized reference glucose measurements, repeated data, independent validation and appropriate review before clinical claims.</p></article><article className="note-card"><span className="note-symbol">◉</span><h3>Current signal baseline</h3><p>{baseline?`Baseline captured on ${fmtDateTime(baseline.capturedAt)}.`:'No baseline captured yet.'} A baseline stores signal values only; it does not calibrate glucose.</p><button className="btn btn-ghost" onClick={()=>setModal('baseline')}>Capture signal baseline</button></article></div></section>}



      {page==='settings' && <section className="section page-section"><div className="section-heading"><div><span className="section-tag">DEVICE CONFIGURATION</span><h2>System settings</h2><p>Configure the local ESP32 sensor API connection.</p></div></div><div className="settings-card">

          <div className="setting-line"><div><b>FastAPI backend</b><p>{backendError || (backendHealth ? 'Backend health endpoint responded.' : 'Checking backend connection…')}</p></div><Pill kind={backendHealth?.status === 'ok' ? 'online' : 'offline'}>{backendHealth?.status === 'ok' ? 'Connected' : 'Unavailable'}</Pill></div>

          <div className="setting-line"><div><b>MongoDB Atlas</b><p>Stored research observations in the backend database.</p></div><Pill kind={backendHealth?.database_connected ? 'online' : 'offline'}>{backendHealth?.database_connected ? 'Connected' : 'Not connected'}</Pill></div>

          <div className="setting-line"><div><b>Research model</b><p>{backendModel?.notice || 'Model artifact status from FastAPI.'}</p></div><Pill kind={backendModel?.available ? 'online' : 'warning'}>{backendModel?.synthetic_demo ? 'Synthetic demo loaded' : backendModel?.available ? 'Artifact found' : 'Not trained'}</Pill></div>

          <div className="setting-line"><div><b>Backend history</b><p>Most recent stored observations returned by FastAPI.</p></div><span className="setting-value">{backendHistory.length} loaded</span></div>

          <form onSubmit={connectIp}><label htmlFor="esp-ip">ESP32 IP address</label><div className="settings-input-row"><input id="esp-ip" value={ipDraft} onChange={e=>setIpDraft(e.target.value)} placeholder="e.g. 10.233.67.4"/><button className="btn btn-primary" type="submit">Apply & connect</button></div><small>Expected endpoint: <code>http://{ip}/api/data</code></small></form><div className="setting-line"><div><b>Connection status</b><p>Current result of the API polling request.</p></div><Pill kind={connection==='connected'?'online':connection==='connecting'?'warning':'offline'}>{connection==='connected'?'Connected':connection==='connecting'?'Connecting':'Disconnected'}</Pill></div><div className="setting-line"><div><b>Refresh interval</b><p>Dashboard polls the ESP32 once per second.</p></div><span className="setting-value">1 second</span></div><div className="setting-line"><div><b>Saved readings</b><p>{saved.length} reading(s) stored locally in this browser.</p></div><button className="btn btn-ghost" onClick={exportCsv}>Export CSV</button></div><div className="setting-line"><div><b>Signal baseline</b><p>{baseline?'A local baseline exists.':'No local baseline saved.'}</p></div><button className="btn btn-ghost" onClick={()=>setModal('baseline')}>Capture baseline</button></div></div></section>}



      <footer className="footer"><span>Glucosense<span className="brand-dot">.</span> Local research dashboard</span><span>Research prototype only · Not a medical device · Do not use for treatment decisions</span></footer>

    </main>



    {modal && <div className="modal-backdrop" role="presentation" onMouseDown={e=>{if(e.target===e.currentTarget)setModal('')}}><section className="modal" role="dialog" aria-modal="true" aria-labelledby="modal-title"><button className="modal-close" onClick={()=>setModal('')} aria-label="Close">×</button><span className="section-tag">SIGNAL TOOLS</span><h2 id="modal-title">{modal==='baseline'?'Capture signal baseline':'Configure device'}</h2>{modal==='baseline'?<><p>Stores the current raw sensor readings as a local reference point for comparing later signals. This does <b>not</b> calibrate or estimate blood glucose.</p><div className="baseline-preview"><span>NIR <b>{fmt(data?.nir ?? channels[3])}</b></span><span>VIS <b>{fmt(data?.vis ?? channels[4])}</b></span><span>Red <b>{fmt(data?.red)}</b></span><span>IR <b>{fmt(data?.ir)}</b></span></div><button className="btn btn-primary full" onClick={calibrateBaseline} disabled={!data}>Save signal baseline</button></>:<button className="btn btn-primary" onClick={()=>{setModal('');setPage('settings')}}>Open settings</button>}<button className="btn btn-ghost full" onClick={()=>setModal('')}>Cancel</button></section></div>}

  </div>;

}
