/**
 * SHRUTI analyst console.
 *
 * Structured around the analyst's workflow rather than as a wall of charts:
 *
 *     overview  ->  ground truth  ->  signal  ->  bits  ->  evidence
 *
 * The overview answers the question in one screen; everything below it is
 * optional depth.  A recorded mission is replayed stage by stage first, so the
 * order in which the engine reached its conclusion is visible, not implied.
 */
import { useCallback, useEffect, useRef, useState, type ReactNode } from 'react'
import * as api from '../lib/api'
import { useStore } from '../lib/store'
import { t, type Key } from '../lib/i18n'
import { go, openMission } from '../lib/route'
import { loadMission, MISSION_PALETTE } from '../lib/missions'
import { refreshEngine } from '../lib/engine'
import { int, pct, scaled, signed } from '../lib/format'
import type { AnalysisResult } from '../lib/types'
import {
  Constellation, ConstellationOrb, EntropyProfile, FunnelBars, Ring, Spectrum, SpectrumArea, Waterfall,
} from './Plots'
import {
  Capabilities, Card, ContainerPanel, FieldTable, GroundTruth, Measurements, Payload, Timings, Verdict,
  WaveformRanking,
} from './Panels'
import { LangToggle, MissionCard } from './Landing'
import { reducedMotion, RocketArt } from './Space'
import * as I from './icons'

const SECTIONS: { id: string; key: Key; icon: typeof I.Overview }[] = [
  { id: 'overview', key: 'navOverview', icon: I.Overview },
  { id: 'truth', key: 'navTruth', icon: I.Target },
  { id: 'signal', key: 'navSignal', icon: I.Wave },
  { id: 'bits', key: 'navBits', icon: I.Binary },
  { id: 'evidence', key: 'navEvidence', icon: I.Shield },
  { id: 'live', key: 'navLive', icon: I.Upload },
]

const scrollTo = (id: string) =>
  document.getElementById(id)?.scrollIntoView({ behavior: reducedMotion() ? 'auto' : 'smooth', block: 'start' })

// ---------------------------------------------------------------------- rails

function LeftRail({ active, present }: { active: string; present: Set<string> }) {
  const lang = useStore((s) => s.lang)
  return (
    <aside className="rail rail-left">
      <a className="rail-logo" href="#/" aria-label={t(lang, 'home')}>
        <I.Logo />
        <span>SHRUTI</span>
      </a>
      <nav className="rail-nav" aria-label="Console sections">
        {SECTIONS.filter((s) => present.has(s.id)).map(({ id, key, icon: Icon }) => (
          <button
            type="button"
            key={id}
            className={active === id ? 'on' : ''}
            aria-current={active === id ? 'true' : undefined}
            onClick={() => scrollTo(id)}
            title={t(lang, key)}
          >
            <span className="nav-ic"><Icon /></span>
            <span className="nav-label">{t(lang, key)}</span>
          </button>
        ))}
      </nav>
      <div className="rail-foot">
        <LangToggle compact />
        <button type="button" className="btn-ghost" onClick={() => go('#/')} title={t(lang, 'home')} aria-label={t(lang, 'home')}>
          <I.Exit />
        </button>
      </div>
    </aside>
  )
}

function RightRail() {
  const lang = useStore((s) => s.lang)
  const missions = useStore((s) => s.catalogue.missions)
  const source = useStore((s) => s.source)
  const engine = useStore((s) => s.engine)
  return (
    <aside className="rail rail-right">
      <div className="rail-missions" role="list" aria-label={t(lang, 'navMissions')}>
        {missions.map((m) => {
          const on = source?.kind === 'mission' && source.id === m.id
          return (
            <button
              type="button"
              role="listitem"
              key={m.id}
              className={`orb-btn orb-${MISSION_PALETTE[m.id] ?? 'violet'} ${on ? 'on' : ''}`}
              onClick={() => openMission(m.id)}
              aria-current={on ? 'true' : undefined}
              title={lang === 'hi' ? m.title_hi : m.title}
              aria-label={lang === 'hi' ? m.title_hi : m.title}
            >
              <span />
            </button>
          )
        })}
        <button
          type="button"
          role="listitem"
          className={`orb-btn orb-live ${source?.kind === 'live' ? 'on' : ''}`}
          onClick={() => scrollTo('live')}
          title={t(lang, 'navLive')}
          aria-label={t(lang, 'navLive')}
        >
          <I.Upload width={18} height={18} />
        </button>
      </div>
      <div className="rail-engine">
        <span>
          {t(lang, 'version')}
          <br />
          <b>{__APP_VERSION__}</b>
        </span>
        {engine.online && (
          <em><span className="engine-dot on" /> {t(lang, 'engine')} {t(lang, 'engineOnline')}</em>
        )}
      </div>
    </aside>
  )
}

// -------------------------------------------------------------------- replay

/**
 * Replays a recorded run in the order the engine reached each conclusion.
 * Every line is read from the result itself; the animation adds no claims.
 */
function DecodeReplay({ res, seconds, onDone }: { res: AnalysisResult; seconds?: number; onDone: () => void }) {
  const lang = useStore((s) => s.lang)
  const p = res.proposals[0]
  const best = res.matches[0]
  const pm = res.plots?.provenance
  const steps: [string, Key, string][] = [
    ['L0', 'stContainer', res.container.summary],
    ['L3', 'stPhysical', p ? `${p.modulation} @ ${p.symbol_rate_bd.toLocaleString(undefined, { maximumFractionDigits: 1 })} Bd · EVM ${p.evm.toFixed(3)}` : '—'],
    ['L5', 'stDemod', pm ? `${int(pm.n_symbols)} ${t(lang, 'symbols')} → ${int(pm.n_bits)} ${t(lang, 'softBits')}` : '—'],
    ['L6', 'stCode', best ? `${best.id} · ${t(lang, 'reencode')} ${pct(best.reencode_agreement)}` : t(lang, 'noMatch')],
    ['L7', 'stFrame', res.frame?.summary ?? '—'],
    ['L8', 'stVerdict', res.verdict],
  ]
  const [n, setN] = useState(0)
  useEffect(() => {
    if (n > steps.length) {
      const id = setTimeout(onDone, 650)
      return () => clearTimeout(id)
    }
    const id = setTimeout(() => setN(n + 1), n === 0 ? 250 : 480)
    return () => clearTimeout(id)
  }, [n, steps.length, onDone])

  return (
    <div className="replay" role="status" aria-live="polite">
      <div className="replay-head">
        <span className="spinner" aria-hidden="true" />
        <div>
          <b>{t(lang, 'replaying')}</b>
          {seconds != null && <span className="muted small"> · {seconds.toFixed(1)} s</span>}
        </div>
        <button type="button" className="btn-ghost small" onClick={onDone}>{t(lang, 'skip')}</button>
      </div>
      <ol className="replay-steps">
        {steps.map(([id, key, text], i) => (
          <li key={id} className={i < n ? 'done' : i === n ? 'now' : ''}>
            <span className="replay-id">{id}</span>
            <span className="replay-name">{t(lang, key)}</span>
            <span className="replay-text mono">{i < n ? text : ''}</span>
          </li>
        ))}
      </ol>
      <div className="replay-bar"><span style={{ width: `${(Math.min(n, steps.length) / steps.length) * 100}%` }} /></div>
    </div>
  )
}

// ------------------------------------------------------------------ overview

function Tile({ icon: Icon, label, value, unit, sub, tone }: {
  icon: typeof I.Overview
  label: string
  value: string
  unit?: string
  sub?: string
  tone: string
}) {
  return (
    <div className={`tile tile-${tone}`}>
      <div className="tile-head"><span className="tile-ic"><Icon width={16} height={16} /></span>{label}</div>
      <b>{value}{unit && <small> {unit}</small>}</b>
      {sub && <span className="tile-sub">{sub}</span>}
    </div>
  )
}

function Overview({ res }: { res: AnalysisResult }) {
  const lang = useStore((s) => s.lang)
  const source = useStore((s) => s.source)
  const missions = useStore((s) => s.catalogue.missions)
  const replaying = useStore((s) => s.replaying)
  const setReplaying = useStore((s) => s.setReplaying)
  const done = useCallback(() => setReplaying(false), [setReplaying])

  const mission = source?.kind === 'mission' ? missions.find((m) => m.id === source.id) : undefined
  const missionNo = mission ? String(missions.indexOf(mission) + 1).padStart(2, '0') : ''
  const palette = source?.kind === 'mission' ? MISSION_PALETTE[source.id] ?? 'violet' : 'violet'
  const p = res.proposals[0]
  const best = res.matches[0]
  const pm = res.plots?.provenance
  const c = res.container
  const gates = res.capabilities.filter((x) => x.available).length

  const [fsV, fsU] = scaled(c.sample_rate, 'S/s')
  const [rsV, rsU] = scaled(p?.symbol_rate_bd, 'Bd')
  const tone = res.verdict === 'IDENTIFIED' ? 'ok' : res.verdict === 'PROBABLE' ? 'warn' : 'bad'

  return (
    <section id="overview" className={`overview ${replaying ? 'is-replaying' : ''}`} aria-busy={replaying}>
      <div className="tiles">
        <Tile icon={I.Hash} tone="slate" label={t(lang, 'samples')} value={int(c.n_samples)} sub={`${c.kind} · ${c.dtype}`} />
        <Tile icon={I.Clock} tone="plum" label={t(lang, 'sampleRate')} value={fsV} unit={fsU} sub={c.rate_basis} />
        <Tile icon={I.Pulse} tone="navy" label={t(lang, 'symbolRate')} value={rsV} unit={rsU} sub={p ? `${p.sps} samples / symbol` : undefined} />
        <Tile icon={I.Compass} tone="bronze" label={t(lang, 'carrierOffset')} value={p ? signed(p.cfo_hz, 1) : '—'} unit="Hz" sub={c.centre_hz ? `tuned ${(c.centre_hz / 1e6).toFixed(3)} MHz` : 'centre unknown'} />
      </div>

      <div className="ov-grid">
        <div className="ov-stage">
          {res.plots?.constellation && res.plots.constellation.i.length > 0 && p ? (
            <ConstellationOrb data={res.plots.constellation} palette={palette} modulation={p.modulation} order={p.order} />
          ) : (
            <div className="orb orb-empty" />
          )}
          <div className="ov-title">
            <span className={`source-badge ${source?.kind ?? ''}`}>
              {source?.kind === 'mission' ? `${t(lang, 'mission')} ${missionNo}` : t(lang, 'liveAnalysis')}
              {mission && ` · ${lang === 'hi' ? mission.title_hi : mission.title}`}
              {source?.kind === 'live' && ` · ${source.label}`}
            </span>
            <h1 className="mega">{p?.modulation ?? res.verdict}</h1>
            <p className="ov-sub">
              {best && res.verdict !== 'UNKNOWN' ? best.id : t(lang, 'noMatch')}
              {p && <> · {p.bits_per_symbol} {t(lang, 'bits')}/{t(lang, 'symbols').replace(/s$/, '')}</>}
            </p>
            <div className="ov-links">
              {res.payload && (
                <button type="button" className="link link-lg" onClick={() => scrollTo('bits')}>
                  <I.Eye width={18} height={18} /> {t(lang, 'readMessage')} <I.ChevronRight width={16} height={16} />
                </button>
              )}
              {source?.kind === 'mission' && !replaying && (
                <button type="button" className="link link-lg" onClick={() => { window.scrollTo(0, 0); setReplaying(true) }}>
                  <I.Refresh width={18} height={18} /> {t(lang, 'replay')}
                </button>
              )}
            </div>
          </div>
        </div>

        <div className="ov-side">
          {res.plots?.spectrum && (
            <div className="glass spec-card">
              <div className="glass-head">
                <span>{t(lang, 'spectrum')}</span>
                <span className="muted small mono">nfft {res.plots.spectrum.nfft}</span>
              </div>
              <SpectrumArea data={res.plots.spectrum} />
            </div>
          )}
          <div className="ov-row">
            <div className="glass funnel-card">
              <div className="glass-head"><span>{t(lang, 'samplesToBits')}</span></div>
              <FunnelBars
                items={[
                  { label: t(lang, 'samples'), value: c.n_samples },
                  { label: t(lang, 'symbols'), value: pm?.n_symbols ?? 0 },
                  { label: t(lang, 'softBits'), value: pm?.n_bits ?? 0 },
                  { label: t(lang, 'payloadBits'), value: res.payload?.n_bits ?? 0 },
                ]}
              />
            </div>
            <div className="ov-verdict">
              <span className={`verdict-pill vp-${tone}`}>{res.verdict}</span>
              <div className="ov-big">
                <b>{best?.reencode_agreement != null ? (best.reencode_agreement * 100).toFixed(1) : '—'}</b>
                <span>%</span>
              </div>
              <span className="muted small">{t(lang, 'reencode')}</span>
            </div>
          </div>
          <div className="glass rings">
            <Ring
              tone="violet" label={t(lang, 'snr')} value={p ? `${p.snr_db.toFixed(1)}` : '—'}
              frac={p ? p.snr_db / 40 : 0}
            />
            <Ring
              tone={p && p.evm > 0.25 ? 'rose' : 'teal'} label={t(lang, 'evm')}
              value={p ? `${(p.evm * 100).toFixed(1)}%` : '—'} frac={p ? p.evm / 0.5 : 0}
            />
            <Ring
              tone="amber" label={t(lang, 'gates')} value={`${gates}/${res.capabilities.length || 0}`}
              frac={res.capabilities.length ? gates / res.capabilities.length : 0}
            />
          </div>
        </div>
      </div>

      {replaying && <DecodeReplay res={res} seconds={mission?.analysis_s} onDone={done} />}
    </section>
  )
}

// ------------------------------------------------------------------- sections

function Section({ id, eyebrow, title, children }: { id: string; eyebrow: string; title: string; children: ReactNode }) {
  return (
    <section id={id} className="c-section">
      <p className="eyebrow">{eyebrow}</p>
      <h2 className="section-title sm">{title}</h2>
      {children}
    </section>
  )
}

// ---------------------------------------------------------------- live engine

function DropZone({ onFile, disabled }: { onFile: (f: File) => void; disabled: boolean }) {
  const lang = useStore((s) => s.lang)
  const [over, setOver] = useState(false)
  const input = useRef<HTMLInputElement>(null)
  return (
    <div
      className={`drop ${over ? 'over' : ''} ${disabled ? 'disabled' : ''}`}
      role="button"
      tabIndex={disabled ? -1 : 0}
      aria-disabled={disabled}
      aria-label={t(lang, 'drop')}
      onKeyDown={(e) => {
        if (!disabled && (e.key === 'Enter' || e.key === ' ')) {
          e.preventDefault()
          input.current?.click()
        }
      }}
      onDragOver={(e) => { e.preventDefault(); if (!disabled) setOver(true) }}
      onDragLeave={() => setOver(false)}
      onDrop={(e) => {
        e.preventDefault()
        setOver(false)
        const f = e.dataTransfer.files?.[0]
        if (f && !disabled) onFile(f)
      }}
      onClick={() => !disabled && input.current?.click()}
    >
      <input
        ref={input} type="file" hidden
        accept=".wav,.iq,.raw,.dat,.bin,.cfile,.cs8,.cs16,.cf32,.sigmf-data,.sigmf-meta"
        onChange={(e) => { const f = e.target.files?.[0]; if (f) onFile(f); e.target.value = '' }}
      />
      <span className="drop-ic"><I.Upload width={28} height={28} /></span>
      <div className="drop-title">{t(lang, 'drop')}</div>
      <div className="drop-hint">{t(lang, 'dropHint')}</div>
    </div>
  )
}

function Live() {
  const lang = useStore((s) => s.lang)
  const busy = useStore((s) => s.busy)
  const stage = useStore((s) => s.stage)
  const error = useStore((s) => s.error)
  const { setResult, setBusy, setError, setSoon } = useStore.getState()
  const [msg, setMsg] = useState('The quick brown fox jumps over the lazy dog.')
  const [holdOut, setHoldOut] = useState(false)

  // Ask the engine before every run: it may have come up since the last check.
  const engineReady = async () => {
    if (useStore.getState().engine.online !== true) await refreshEngine()
    return useStore.getState().engine.online === true
  }

  const finish = (r: AnalysisResult, label: string) => {
    setResult(r, { kind: 'live', label })
    go('#/console')
    requestAnimationFrame(() => scrollTo('overview'))
  }

  const onFile = async (f: File) => {
    if (!(await engineReady())) {
      setSoon({ kind: 'file', name: f.name })
      return
    }
    setBusy(true, `reading ${f.name}`)
    try {
      finish(await api.analyse(f), f.name)
    } catch (e) {
      setError(String(e))
    } finally {
      setBusy(false)
    }
  }

  const runSelfTest = async () => {
    if (!(await engineReady())) {
      setSoon({ kind: 'selftest' })
      return
    }
    setBusy(true, 'randomising the transmitter')
    try {
      const r = await api.runSelfTest({
        message: msg,
        seed: Math.floor(Math.random() * 1e9),
        hold_out: holdOut ? 'self' : null,
      })
      finish(r, t(lang, 'selftest'))
    } catch (e) {
      setError(String(e))
    } finally {
      setBusy(false)
    }
  }

  return (
    <>
      {busy && (
        <div className="busy" role="status"><span className="spinner" />{t(lang, 'analysing')}… {stage}</div>
      )}
      {error && <div className="error" role="alert">{error}</div>}
      <div className="live-grid">
        <DropZone onFile={onFile} disabled={busy} />
        <Card title={t(lang, 'selftest')} className="selftest">
          <p className="muted small">{t(lang, 'selftestBody')}</p>
          <label className="field">
            <span className="sr-only">{t(lang, 'yourSentence')}</span>
            <input value={msg} onChange={(e) => setMsg(e.target.value)} placeholder={t(lang, 'yourSentence')} />
          </label>
          <label className="check">
            <input type="checkbox" checked={holdOut} onChange={(e) => setHoldOut(e.target.checked)} />
            {t(lang, 'holdOut')}
          </label>
          <button type="button" className="btn-primary" onClick={runSelfTest} disabled={busy || !msg.trim()}>
            <I.Dice width={18} height={18} /> {t(lang, 'runSelfTest')}
          </button>
        </Card>
      </div>
    </>
  )
}

/**
 * Shown when a visitor asks for live analysis and no engine answers.  The
 * engine is built to run air-gapped on the analyst's own machine; this says,
 * warmly, that live analysis comes with the final release, and points at the
 * two missions in the meantime.
 */
function ComingSoon() {
  const lang = useStore((s) => s.lang)
  const soon = useStore((s) => s.soon)
  const setSoon = useStore((s) => s.setSoon)
  const missions = useStore((s) => s.catalogue.missions)
  const closeRef = useRef<HTMLButtonElement>(null)

  useEffect(() => {
    if (!soon) return
    closeRef.current?.focus()
    const onKey = (e: KeyboardEvent) => { if (e.key === 'Escape') setSoon(null) }
    window.addEventListener('keydown', onKey)
    return () => window.removeEventListener('keydown', onKey)
  }, [soon, setSoon])

  if (!soon) return null
  const lead = soon.kind === 'file' ? t(lang, 'soonFile').replace('{name}', soon.name) : t(lang, 'soonSelftest')
  return (
    <div className="soon-backdrop" onClick={() => setSoon(null)}>
      <div
        className="soon" role="dialog" aria-modal="true" aria-labelledby="soon-title"
        onClick={(e) => e.stopPropagation()}
      >
        <RocketArt />
        <p className="soon-lead">{lead}</p>
        <h2 id="soon-title">{t(lang, 'soonTitle')}</h2>
        <p className="soon-body">{t(lang, 'soonBody')}</p>
        <div className="soon-actions">
          {missions.map((m) => (
            <button
              type="button"
              key={m.id}
              className={`btn-primary ${MISSION_PALETTE[m.id] === 'earth' ? 'btn-earth' : ''}`}
              onClick={() => { setSoon(null); openMission(m.id) }}
            >
              {lang === 'hi' ? m.title_hi : m.title}
              <I.ArrowRight width={18} height={18} />
            </button>
          ))}
          <button type="button" ref={closeRef} className="btn-ghost small" onClick={() => setSoon(null)}>
            {t(lang, 'gotIt')}
          </button>
        </div>
      </div>
    </div>
  )
}

// ---------------------------------------------------------------------- page

export function Console({ missionId }: { missionId?: string }) {
  const lang = useStore((s) => s.lang)
  const result = useStore((s) => s.result)
  const missions = useStore((s) => s.catalogue.missions)
  const [active, setActive] = useState('overview')

  // Load the mission named in the route, unless it is already on screen.
  useEffect(() => {
    if (!missionId) return
    const { source: cur, result: have, setBusy, setResult, setError, setReplaying } = useStore.getState()
    if (have && cur?.kind === 'mission' && cur.id === missionId) return
    let cancelled = false
    setBusy(true, 'loading mission')
    loadMission(missionId)
      .then((r) => {
        if (cancelled) return
        setResult(r, { kind: 'mission', id: missionId })
        setReplaying(!reducedMotion())
        window.scrollTo(0, 0)
      })
      .catch((e) => !cancelled && setError(String(e)))
      .finally(() => !cancelled && setBusy(false))
    return () => { cancelled = true }
  }, [missionId])

  const present = new Set(['live'])
  if (result) {
    present.add('overview').add('signal').add('bits').add('evidence')
    if (result.selftest) present.add('truth')
  }

  // Scroll-spy for the left rail.
  useEffect(() => {
    const els = SECTIONS.map((s) => document.getElementById(s.id)).filter(Boolean) as HTMLElement[]
    const io = new IntersectionObserver(
      (entries) => {
        for (const e of entries) if (e.isIntersecting) setActive(e.target.id)
      },
      { rootMargin: '-35% 0px -60% 0px' },
    )
    els.forEach((el) => io.observe(el))
    return () => io.disconnect()
  }, [result])

  return (
    <div className="console">
      <LeftRail active={result ? active : 'live'} present={present} />
      <main className="console-main">
        {result ? (
          <>
            <Overview res={result} />

            {result.selftest && (
              <Section id="truth" eyebrow={t(lang, 'truthEyebrow')} title={t(lang, 'truthTitle')}>
                <GroundTruth res={result} />
              </Section>
            )}

            <Section id="signal" eyebrow={t(lang, 'signalEyebrow')} title={t(lang, 'signalTitle')}>
              <div className="plots-grid">
                {result.plots?.spectrum && (
                  <Card title={t(lang, 'spectrum')}><Spectrum data={result.plots.spectrum} /></Card>
                )}
                {result.plots?.constellation && (
                  <Card title={t(lang, 'constellation')}><Constellation data={result.plots.constellation} /></Card>
                )}
                {result.plots?.waterfall && (
                  <Card
                    title={t(lang, 'waterfall')} className="span-2"
                    aside={<span className="muted small mono">{result.plots.waterfall.duration_s.toFixed(3)} s</span>}
                  >
                    <Waterfall data={result.plots.waterfall} />
                  </Card>
                )}
              </div>
            </Section>

            <Section id="bits" eyebrow={t(lang, 'bitsEyebrow')} title={t(lang, 'bitsTitle')}>
              <div className="plots-grid">
                {result.fieldmap && (
                  <Card title={t(lang, 'entropy')} className="span-2"><EntropyProfile fieldmap={result.fieldmap} /></Card>
                )}
                <Payload res={result} />
                {result.fieldmap && <FieldTable fieldmap={result.fieldmap} />}
              </div>
            </Section>

            <Section id="evidence" eyebrow={t(lang, 'evidenceEyebrow')} title={t(lang, 'evidenceTitle')}>
              <Verdict res={result} />
              <div className="panel-grid">
                <ContainerPanel res={result} />
                <Measurements proposals={result.proposals} />
                <WaveformRanking matches={result.matches} />
                <Capabilities caps={result.capabilities} />
                <Timings timings={result.timings} />
                {result.notes.length > 0 && (
                  <Card title={t(lang, 'notes')}>
                    <ul className="notes">{result.notes.map((n, i) => <li key={i}>{n}</li>)}</ul>
                  </Card>
                )}
              </div>
            </Section>
          </>
        ) : (
          <section className="c-empty">
            <p className="eyebrow">{t(lang, 'navOverview')}</p>
            <h1 className="section-title">{t(lang, 'emptyTitle')}</h1>
            <p className="section-body">{t(lang, 'emptyBody')}</p>
            <div className="mission-grid">
              {missions.map((m, i) => <MissionCard key={m.id} m={m} index={i} />)}
            </div>
          </section>
        )}

        <Section id="live" eyebrow={t(lang, 'liveEyebrow')} title={t(lang, 'liveTitle')}>
          <Live />
        </Section>

      </main>
      <RightRail />
      <ComingSoon />
    </div>
  )
}
