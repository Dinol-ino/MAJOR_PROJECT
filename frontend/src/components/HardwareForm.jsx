import React, { useCallback, useEffect, useRef, useState } from 'react';
import { apiClient } from '../api/client';

/**
 * Hardware & Models.
 * Every value shown comes from the backend: live telemetry (authenticated SSE with bounded
 * back-off), the runtime's installed models, and registry recommendations evaluated against
 * the detected hardware. Unknown values are shown as unknown, never as placeholders.
 */
export default function HardwareForm({ activeModel, onModelsChanged, onActivateModel }) {
  const [telemetry, setTelemetry] = useState(null);
  const [streamState, setStreamState] = useState('connecting'); // connecting | live | retrying
  const [recommend, setRecommend] = useState(null);
  const [recommendError, setRecommendError] = useState('');
  const [installed, setInstalled] = useState(null);
  const [job, setJob] = useState(null);
  const [actionError, setActionError] = useState('');
  const [busyModel, setBusyModel] = useState(null);
  const jobStreamRef = useRef(null);

  // ---- telemetry: one authenticated stream, exponential back-off, cleaned up on unmount
  useEffect(() => {
    let cancelled = false;
    let controller = null;
    let timer = null;
    let attempt = 0;

    apiClient.getTelemetrySample().then((d) => !cancelled && setTelemetry(d)).catch(() => {});

    const connect = () => {
      if (cancelled) return;
      setStreamState(attempt === 0 ? 'connecting' : 'retrying');
      controller = apiClient.streamTelemetry({
        onOpen: () => { attempt = 0; setStreamState('live'); },
        onEvent: (d) => { if (!cancelled && d && d.cpu) setTelemetry(d); },
        onError: () => scheduleReconnect(),
        onClose: () => scheduleReconnect(),
      });
    };
    const scheduleReconnect = () => {
      if (cancelled) return;
      attempt += 1;
      setStreamState('retrying');
      const delay = Math.min(30000, 1000 * 2 ** Math.min(attempt, 5));
      timer = setTimeout(connect, delay);
    };
    connect();
    return () => {
      cancelled = true;
      if (controller) controller.abort();
      if (timer) clearTimeout(timer);
    };
  }, []);

  const loadModels = useCallback(async () => {
    setRecommendError('');
    try {
      const [rec, inst] = await Promise.all([apiClient.getRecommendedModels(), apiClient.getInstalledModels()]);
      setRecommend(rec);
      setInstalled(inst);
    } catch (err) {
      setRecommendError(err.message || 'Could not load models.');
    }
  }, []);

  useEffect(() => { loadModels(); }, [loadModels]);

  const followJob = useCallback((jobId) => {
    if (jobStreamRef.current) jobStreamRef.current.abort();
    jobStreamRef.current = apiClient.streamProvisioningProgress(
      jobId,
      (p) => setJob(p),
      async (p) => { setJob(p); await loadModels(); if (onModelsChanged) onModelsChanged(); },
      (err) => { setJob((j) => (j ? { ...j, status: j.status === 'ready' ? 'ready' : 'failed', error: j.error || err.message } : j)); loadModels(); },
    );
  }, [loadModels, onModelsChanged]);

  // Resume a download that is still running (e.g. after a page refresh).
  useEffect(() => {
    apiClient.getActiveProvisioningJob().then((j) => {
      if (j && j.job_id && !['ready', 'failed', 'cancelled', 'none'].includes(j.status)) {
        setJob(j);
        followJob(j.job_id);
      }
    }).catch(() => {});
    return () => { if (jobStreamRef.current) jobStreamRef.current.abort(); };
  }, [followJob]);

  const downloadAndActivate = async (modelId) => {
    setActionError('');
    setBusyModel(modelId);
    try {
      const res = await apiClient.startProvisioning(modelId, false, true);
      if (res.job_id) {
        setJob({ job_id: res.job_id, model_id: modelId, status: res.status, percent: res.percent || 0, message: res.message });
        followJob(res.job_id);
      }
    } catch (err) {
      setActionError(err.message);
    } finally {
      setBusyModel(null);
    }
  };

  const activate = async (name) => {
    setActionError('');
    setBusyModel(name);
    try {
      await onActivateModel(name);
      await loadModels();
    } catch (err) {
      setActionError(err.message);
    } finally {
      setBusyModel(null);
    }
  };

  const cancelJob = async () => {
    if (!job?.job_id) return;
    try { await apiClient.cancelProvisioningJob(job.job_id); } catch (err) { setActionError(err.message); }
  };

  const jobRunning = job && !['ready', 'failed', 'cancelled'].includes(job.status);

  return (
    <div style={st.page}>
      <section style={st.section}>
        <div style={st.sectionHead}>
          <h2 style={st.h2}>This machine</h2>
          <span style={st.muted}>
            {streamState === 'live' ? 'Live' : streamState === 'retrying' ? 'Reconnecting…' : 'Connecting…'}
            {telemetry?.ts ? ` · updated ${new Date(telemetry.ts * 1000).toLocaleTimeString()}` : ''}
          </span>
        </div>
        <div style={st.grid}>
          <Metric label="Processor" value={telemetry?.cpu?.name} sub={telemetry?.cpu ? `${telemetry.cpu.cores_physical} cores / ${telemetry.cpu.cores_logical} threads · ${telemetry.cpu.load_percent}% load` : null} />
          <Metric label="Memory" value={telemetry?.ram ? `${telemetry.ram.available_gb} GB free` : null} sub={telemetry?.ram ? `of ${telemetry.ram.total_gb} GB` : null} />
          <Metric
            label="GPU"
            value={telemetry?.gpu ? (telemetry.gpu.status === 'probing' ? 'Probing…' : telemetry.gpu.detected ? telemetry.gpu.name : 'None detected') : null}
            sub={telemetry?.gpu?.detected
              ? (telemetry.gpu.vram_reliable ? `${telemetry.gpu.vram_total_gb} GB VRAM · ${telemetry.gpu.backend}` : 'VRAM unknown (not used for sizing)')
              : telemetry?.gpu?.reason}
          />
          <Metric label="Disk (model store)" value={telemetry?.disk?.free_gb != null ? `${telemetry.disk.free_gb} GB free` : telemetry ? 'Unavailable' : null} sub={telemetry?.disk?.total_gb != null ? `of ${telemetry.disk.total_gb} GB` : null} />
        </div>
        {telemetry?.tier?.reason && <p style={st.note}>{telemetry.tier.reason}</p>}
      </section>

      <section style={st.section}>
        <div style={st.sectionHead}>
          <h2 style={st.h2}>Installed models</h2>
          <span style={st.muted}>{installed ? (installed.runtime_online ? 'Runtime reachable' : 'Runtime not reachable') : 'Loading…'}</span>
        </div>
        {installed && !installed.runtime_online && (
          <p style={st.warn}>The local model runtime (Ollama) is not reachable, so no model can answer. Start Ollama, then reload this page.</p>
        )}
        {installed?.models?.length === 0 && installed.runtime_online && (
          <p style={st.note}>No models are installed yet. Download a recommended model below.</p>
        )}
        {(installed?.models || []).map((m) => (
          <Row
            key={m.name}
            title={m.name}
            meta={[m.parameter_size, m.quantization, m.size_bytes ? `${(m.size_bytes / 1e9).toFixed(1)} GB` : null].filter(Boolean).join(' · ')}
            detail={m.fit_reason}
            tag={m.name === activeModel ? 'Active' : m.safety_tier !== 'SAFE' ? m.safety_tier : null}
            action={m.name === activeModel ? null : (
              <button type="button" style={st.btn} disabled={!!busyModel} onClick={() => activate(m.name)}>
                {busyModel === m.name ? 'Loading…' : 'Activate'}
              </button>
            )}
          />
        ))}
      </section>

      {job && (
        <section style={st.section} aria-live="polite">
          <div style={st.sectionHead}>
            <h2 style={st.h2}>Download: {job.model_id}</h2>
            <span style={st.muted}>{job.status}</span>
          </div>
          <div style={st.track}><div style={{ ...st.fill, width: `${Math.max(0, Math.min(100, job.percent || 0))}%` }} /></div>
          <p style={st.note}>
            {job.message}
            {job.speed_mbps ? ` · ${job.speed_mbps} MB/s` : ''}
            {job.retries ? ` · retry ${job.retries}` : ''}
          </p>
          {job.error && <p style={st.warn}>{job.error}</p>}
          {jobRunning && <button type="button" style={st.btnGhost} onClick={cancelJob}>Cancel download</button>}
        </section>
      )}

      <section style={st.section}>
        <div style={st.sectionHead}>
          <h2 style={st.h2}>Recommended for this machine</h2>
          <span style={st.muted}>From the model registry, sized against detected memory and disk</span>
        </div>
        {recommendError && <p style={st.warn}>{recommendError}</p>}
        {actionError && <p role="alert" style={st.warn}>{actionError}</p>}
        {(recommend?.recommended || []).map((m) => (
          <Row
            key={m.model_id}
            title={m.display_name}
            meta={[m.parameter_size, m.quantization, `~${m.size_gb} GB download`, `needs ~${m.ram_required_gb} GB RAM`, m.license].filter(Boolean).join(' · ')}
            detail={m.fits_storage ? m.fit_reason : `Not enough free disk (needs ~${m.storage_required_gb} GB).`}
            tag={m.installed ? 'Installed' : m.recommended_for_tier ? 'Recommended' : m.safety_tier === 'UNSUPPORTED' ? 'Too large' : m.safety_tier === 'CAUTION' ? 'Tight fit' : null}
            action={m.installed ? null : (
              <button
                type="button"
                style={st.btn}
                disabled={!m.downloadable || jobRunning || !!busyModel || !recommend?.ollama_online}
                title={!recommend?.ollama_online ? 'The model runtime is not reachable' : !m.downloadable ? 'Not safe for this machine' : ''}
                onClick={() => downloadAndActivate(m.model_id)}
              >
                Download &amp; activate
              </button>
            )}
          />
        ))}
      </section>
    </div>
  );
}

function Metric({ label, value, sub }) {
  return (
    <div style={st.metric}>
      <div style={st.metricLabel}>{label}</div>
      <div style={st.metricValue}>{value ?? <span style={{ color: 'var(--text-muted)' }}>Waiting for first sample…</span>}</div>
      {sub && <div style={st.metricSub}>{sub}</div>}
    </div>
  );
}

function Row({ title, meta, detail, tag, action }) {
  return (
    <div style={st.row}>
      <div style={{ flex: 1, minWidth: 0 }}>
        <div style={st.rowTitle}>{title}{tag && <span style={st.tag}>{tag}</span>}</div>
        {meta && <div style={st.rowMeta}>{meta}</div>}
        {detail && <div style={st.rowDetail}>{detail}</div>}
      </div>
      {action}
    </div>
  );
}

const st = {
  page: { height: '100%', overflowY: 'auto', padding: '28px 40px 64px', maxWidth: 980 },
  section: { borderTop: '1px solid var(--border-subtle)', padding: '20px 0 8px' },
  sectionHead: { display: 'flex', alignItems: 'baseline', justifyContent: 'space-between', gap: 12, marginBottom: 12 },
  h2: { fontFamily: 'var(--font-serif)', fontWeight: 600, fontSize: '1.15rem' },
  muted: { color: 'var(--text-muted)', fontSize: '0.78rem' },
  grid: { display: 'grid', gridTemplateColumns: 'repeat(auto-fit, minmax(200px, 1fr))', gap: 16 },
  metric: { border: '1px solid var(--border-subtle)', borderRadius: 'var(--radius-md)', padding: '12px 14px' },
  metricLabel: { color: 'var(--text-muted)', fontSize: '0.72rem', textTransform: 'uppercase', letterSpacing: '0.08em', marginBottom: 6 },
  metricValue: { fontSize: '0.95rem', color: 'var(--text-primary)' },
  metricSub: { color: 'var(--text-muted)', fontSize: '0.76rem', marginTop: 4 },
  note: { color: 'var(--text-secondary)', fontSize: '0.85rem', margin: '10px 0' },
  warn: { color: 'var(--status-amber)', fontSize: '0.85rem', margin: '10px 0' },
  row: { display: 'flex', alignItems: 'center', gap: 16, padding: '12px 0', borderBottom: '1px solid var(--border-subtle)' },
  rowTitle: { fontSize: '0.95rem', color: 'var(--text-primary)', display: 'flex', alignItems: 'center', gap: 8 },
  rowMeta: { color: 'var(--text-muted)', fontSize: '0.78rem', marginTop: 3 },
  rowDetail: { color: 'var(--text-secondary)', fontSize: '0.8rem', marginTop: 3 },
  tag: { fontSize: '0.68rem', color: 'var(--accent)', border: '1px solid var(--accent-blue-border)', borderRadius: 'var(--radius-full)', padding: '1px 8px' },
  btn: { background: 'transparent', border: '1px solid var(--accent)', color: 'var(--accent)', borderRadius: 'var(--radius-sm)', padding: '6px 12px', cursor: 'pointer', fontSize: '0.8rem', whiteSpace: 'nowrap' },
  btnGhost: { background: 'transparent', border: '1px solid var(--border-medium)', color: 'var(--text-secondary)', borderRadius: 'var(--radius-sm)', padding: '6px 12px', cursor: 'pointer', fontSize: '0.8rem' },
  track: { height: 4, background: 'var(--bg-raised)', borderRadius: 2, overflow: 'hidden' },
  fill: { height: '100%', background: 'var(--accent)', transition: 'width 0.4s ease' },
};
