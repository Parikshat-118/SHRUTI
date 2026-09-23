/**
 * The landing page: what SHRUTI is, the two recorded missions, and how the
 * pipeline gets from samples to bits.  Every figure on it comes from the
 * library or the recorded runs — nothing here is decorative data.
 */
import { useEffect, useState } from 'react'
import { useStore } from '../lib/store'
import { LAYERS, t } from '../lib/i18n'
import { go, openMission } from '../lib/route'
import { MISSION_PALETTE, type MissionMeta } from '../lib/missions'
import { hz } from '../lib/format'
import { CarrierWaves, Planet, SatelliteArt, reducedMotion } from './Space'
import { Sparkline } from './Plots'
import * as I from './icons'

const scrollTo = (id: string) =>
  document.getElementById(id)?.scrollIntoView({ behavior: reducedMotion() ? 'auto' : 'smooth', block: 'start' })

/**
 * Bring the mission cards and the note beneath them fully into view: centred
 * in the space under the fixed header when they fit, top-aligned under it when
 * the window is too short for all of them.
 */
function revealMissions() {
  const grid = document.querySelector('#missions .mission-grid')
  if (!grid) return
  const last = document.querySelector('#missions .demo-note') ?? grid
  const header = document.querySelector('.topnav')?.getBoundingClientRect().height ?? 0
  const top = grid.getBoundingClientRect().top + window.scrollY
  const bottom = last.getBoundingClientRect().bottom + window.scrollY
  const room = window.innerHeight - header
  const gap = bottom - top < room ? (room - (bottom - top)) / 2 : 24
  window.scrollTo({ top: top - header - gap, behavior: reducedMotion() ? 'auto' : 'smooth' })
}

export function LangToggle({ compact = false }: { compact?: boolean }) {
  const lang = useStore((s) => s.lang)
  const setLang = useStore((s) => s.setLang)
  return (
    <button
      type="button"
      className={`btn-ghost lang ${compact ? 'compact' : ''}`}
      onClick={() => setLang(lang === 'en' ? 'hi' : 'en')}
      aria-label={lang === 'en' ? 'हिन्दी में देखें' : 'View in English'}
      title={lang === 'en' ? 'हिन्दी' : 'English'}
    >
      <I.Globe width={18} height={18} />
      {!compact && <span>{t(lang, 'language')}</span>}
    </button>
  )
}

/** Where "launch" goes: straight into the first mission, so nobody lands on an empty console. */
function useLaunch() {
  const first = useStore((s) => s.catalogue.missions[0]?.id)
  return () => (first ? openMission(first) : go('#/console'))
}

function NavBar() {
  const lang = useStore((s) => s.lang)
  const launch = useLaunch()
  const [solid, setSolid] = useState(false)
  useEffect(() => {
    const on = () => setSolid(window.scrollY > 40)
    on()
    window.addEventListener('scroll', on, { passive: true })
    return () => window.removeEventListener('scroll', on)
  }, [])
  return (
    <header className={`topnav ${solid ? 'solid' : ''}`}>
      <a className="wordmark" href="#/" aria-label="SHRUTI home">
        <I.Logo />
        <span>SHRUTI</span>
      </a>
      <nav aria-label="Sections">
        <button type="button" onClick={revealMissions}>{t(lang, 'navMissions')}</button>
        <button type="button" onClick={() => scrollTo('how')}>{t(lang, 'navHow')}</button>
        <button type="button" onClick={() => scrollTo('principles')}>{t(lang, 'navPrinciples')}</button>
      </nav>
      <div className="topnav-right">
        <LangToggle />
        <button type="button" className="btn-outline" onClick={launch}>{t(lang, 'launch')}</button>
      </div>
    </header>
  )
}

function Hero() {
  const lang = useStore((s) => s.lang)
  return (
    <section className="hero">
      <CarrierWaves />
      <Planet palette="earth" size={150} seed={9} className="hero-earth" />
      <SatelliteArt className="hero-sat" />
      <div className="hero-copy">
        <p className="hero-eyebrow">{t(lang, 'heroEyebrow')}</p>
        <h1 className="display">
          <span>{t(lang, 'heroLine1')}</span>
          <span className="display-alt">{t(lang, 'heroLine2')}</span>
        </h1>
        <p className="hero-body">{t(lang, 'heroBody')}</p>
        <div className="hero-ctas">
          <button type="button" className="btn-primary" onClick={revealMissions}>
            {t(lang, 'explore')}
            <I.ArrowRight width={18} height={18} />
          </button>
          <button type="button" className="btn-outline btn-pill" onClick={() => scrollTo('how')}>
            <span className="btn-ic"><I.ChevronDown width={16} height={16} /></span>
            {t(lang, 'discover')}
          </button>
        </div>
      </div>
      <Planet palette="violet" size="min(1180px, 130vw)" seed={4} grid className="hero-planet" />
    </section>
  )
}

function Stats() {
  const lang = useStore((s) => s.lang)
  const cartridges = useStore((s) => s.engine.cartridges || s.catalogue.cartridges)
  const stats: [string, string, string][] = [
    [cartridges ? String(cartridges) : '—', t(lang, 'statCartridges'), 'violet'],
    ['9', t(lang, 'statModulations'), 'plum'],
    ['4', t(lang, 'statInterleavers'), 'navy'],
    ['0', t(lang, 'statEgress'), 'bronze'],
  ]
  return (
    <section className="stats" aria-label="At a glance">
      {stats.map(([v, k, tone]) => (
        <div key={k} className={`tile tile-${tone}`}>
          <b>{v}</b>
          <span>{k}</span>
        </div>
      ))}
    </section>
  )
}

export function MissionCard({ m, index }: { m: MissionMeta; index: number }) {
  const lang = useStore((s) => s.lang)
  const palette = MISSION_PALETTE[m.id] ?? 'violet'
  return (
    <article className={`mission-card mc-${palette}`}>
      <div className="mc-top">
        <span className="mc-num">{t(lang, 'mission')} {String(index + 1).padStart(2, '0')}</span>
        <span className="chip">{m.band}</span>
      </div>
      <Planet palette={palette} size={168} seed={palette === 'earth' ? 11 : 5} className="mc-planet" rings={palette === 'mars'} />
      <h3>{lang === 'hi' ? m.title_hi : m.title}</h3>
      <p className="mc-tag">{lang === 'hi' ? m.tagline_hi : m.tagline}</p>
      <div className="mc-spark">
        <Sparkline values={m.preview} id={m.id} />
      </div>
      <dl className="mc-meta">
        <div><dt>file</dt><dd className="mono">{m.file}</dd></div>
        <div><dt>container</dt><dd>{m.container}</dd></div>
        {m.centre_hz ? <div><dt>tuned</dt><dd className="mono">{hz(m.centre_hz, 2)}</dd></div> : null}
      </dl>
      <button type="button" className="btn-primary" onClick={() => openMission(m.id)}>
        {t(lang, 'decode')}
        <I.ArrowRight width={18} height={18} />
      </button>
      <p className="mc-foot">{t(lang, 'analysisTime')} · {m.analysis_s.toFixed(1)} s</p>
    </article>
  )
}

function Missions() {
  const lang = useStore((s) => s.lang)
  const missions = useStore((s) => s.catalogue.missions)
  return (
    <section id="missions" className="section">
      <p className="eyebrow">{t(lang, 'missionsEyebrow')}</p>
      <h2 className="section-title">{t(lang, 'missionsTitle')}</h2>
      <p className="section-body">{t(lang, 'missionsBody')}</p>
      <div className="mission-grid">
        {missions.map((m, i) => <MissionCard key={m.id} m={m} index={i} />)}
        {!missions.length && <div className="card muted">Loading missions…</div>}
      </div>
    </section>
  )
}

function HowItWorks() {
  const lang = useStore((s) => s.lang)
  return (
    <section id="how" className="section">
      <p className="eyebrow">{t(lang, 'howEyebrow')}</p>
      <h2 className="section-title">{t(lang, 'howTitle')}</h2>
      <p className="section-body">{t(lang, 'howBody')}</p>
      <div className="pipeline">
        <div className="pipe-track" aria-hidden="true">
          <span className="pipe-packet" />
        </div>
        <ol className="pipe-nodes">
          {LAYERS.map((l) => {
            const [name, body] = lang === 'hi' ? l.hi : l.en
            return (
              <li key={l.id} className={l.id === 'L4' ? 'core' : ''}>
                <span className="pipe-dot">{l.id}</span>
                <b>{name}</b>
                <span>{body}</span>
              </li>
            )
          })}
        </ol>
        <svg className="pipe-feedback" viewBox="0 0 1000 70" preserveAspectRatio="none" aria-hidden="true">
          <path d="M 1000 0 C 1000 58, 930 62, 500 62 C 70 62, 0 58, 0 0" />
        </svg>
        <p className="pipe-caption">↺ {t(lang, 'closure')}</p>
      </div>
    </section>
  )
}

function Principles() {
  const lang = useStore((s) => s.lang)
  const items: [typeof I.Target, 'p1' | 'p2' | 'p3' | 'p4'][] = [
    [I.Refresh, 'p1'], [I.Dice, 'p2'], [I.Shield, 'p3'], [I.Eye, 'p4'],
  ]
  return (
    <section id="principles" className="section">
      <p className="eyebrow">{t(lang, 'principlesEyebrow')}</p>
      <h2 className="section-title">{t(lang, 'principlesTitle')}</h2>
      <div className="principles">
        {items.map(([Icon, k]) => (
          <div key={k} className="card principle">
            <span className="principle-ic"><Icon width={22} height={22} /></span>
            <h3>{t(lang, `${k}Title`)}</h3>
            <p>{t(lang, `${k}Body`)}</p>
          </div>
        ))}
      </div>
    </section>
  )
}

export function Landing() {
  const lang = useStore((s) => s.lang)
  return (
    <div className="landing">
      <NavBar />
      <Hero />
      <Stats />
      <Missions />
      <HowItWorks />
      <Principles />
      <footer className="site-foot">
        <span className="wordmark small"><I.Logo width={20} height={20} /> SHRUTI v{__APP_VERSION__}</span>
        <span>{t(lang, 'subtitle')}</span>
      </footer>
    </div>
  )
}
