/**
 * SHRUTI analyst interface.
 *
 * Structured around the analyst's workflow rather than as a wall of charts:
 *
 *     triage  ->  drill  ->  decode  ->  export
 *
 * Three clicks to an answer: drop a file, read one screen, export. Everything
 * else is optional depth behind a disclosure.
 */
import { useCallback, useEffect, useRef, useState } from 'react'
import * as api from './lib/api'
import { useStore } from './lib/store'
import { t } from './lib/i18n'
import { Constellation, EntropyProfile, Spectrum, Waterfall } from './components/Plots'
import {
  Capabilities, ContainerPanel, FieldTable, Measurements, Payload, Verdict, WaveformRanking,
} from './components/Panels'

function DropZone({ onFile }: { onFile: (f: File) => void }) {
  const lang = useStore((s) => s.lang)
  const [over, setOver] = useState(false)
  const input = useRef<HTMLInputElement>(null)
  return (
    <div
      className={`drop ${over ? 'over' : ''}`}
      role="button"
      tabIndex={0}
      aria-label={t(lang, 'drop')}
      onKeyDown={(e) => {
        if (e.key === 'Enter' || e.key === ' ') {
          e.preventDefault()
          input.current?.click()
        }
      }}
      onDragOver={(e) => { e.preventDefault(); setOver(true) }}
      onDragLeave={() => setOver(false)}
      onDrop={(e) => {
        e.preventDefault(); setOver(false)
        const f = e.dataTransfer.files?.[0]
        if (f) onFile(f)
      }}
      onClick={() => input.current?.click()}
    >
      <input
        ref={input} type="file" hidden
        accept=".wav,.iq,.raw,.dat,.bin,.cfile,.cs8,.cs16,.cf32,.sigmf-data,.sigmf-meta"
        onChange={(e) => { const f = e.target.files?.[0]; if (f) onFile(f) }}
      />
      <svg className="drop-icon" viewBox="0 0 40 40" fill="none" stroke="currentColor" strokeWidth="1.6" aria-hidden="true">
        <path d="M20 26V7m-7 7 7-7 7 7M8 25v7a2 2 0 0 0 2 2h20a2 2 0 0 0 2-2v-7" strokeLinecap="round" strokeLinejoin="round" />
      </svg>
      <div className="drop-title">{t(lang, 'drop')}</div>
      <div className="drop-hint">{t(lang, 'dropHint')}</div>
    </div>
  )
}

function SelfTestPanel() {
  const lang = useStore((s) => s.lang)
  const setResult = useStore((s) => s.setResult)
  const setBusy = useStore((s) => s.setBusy)
  const setError = useStore((s) => s.setError)
  const [msg, setMsg] = useState('The quick brown fox jumps over the lazy dog.')
  const [holdOut, setHoldOut] = useState(false)

  const run = async () => {
    setBusy(true, 'randomising the transmitter')
    try {
      const r = await api.runSelfTest({
        message: msg,
        seed: Math.floor(Math.random() * 1e9),
        hold_out: null,
      })
      setResult(r)
    } catch (e) {
      setError(String(e))
    } finally {
      setBusy(false)
    }
  }

  return (
    <section className="panel selftest">
      <h3>{t(lang, 'selftest')}</h3>
      <p className="muted small">
        Enter a sentence. The transmitter picks a random modulation, symbol rate,
        interleaver and code — then SHRUTI is handed an unlabelled file and told nothing.
      </p>
      <input
        className="sentence" value={msg} onChange={(e) => setMsg(e.target.value)}
        placeholder={t(lang, 'yourSentence')}
      />
      <label className="check">
        <input type="checkbox" checked={holdOut} onChange={(e) => setHoldOut(e.target.checked)} />
        hold out the cartridge (a genuine blind test)
      </label>
      <button className="primary" onClick={run}>{t(lang, 'runSelfTest')}</button>
    </section>
  )
}

function SelfTestOutcomeBanner() {
  const selftest = useStore((s) => s.result?.selftest)
  if (!selftest) return null
  return (
    <div className={`selftest-outcome ${selftest.success ? 'ok' : 'bad'}`}>
      <div className="row"><span>transmitted</span><b>{selftest.message}</b></div>
      <div className="row"><span>SHRUTI recovered</span><b>{selftest.recovered.slice(0, 90)}</b></div>
      <div className="row">
        <span>the transmitter was</span>
        <b>
          {selftest.transmitter.cartridge_id} · SNR {selftest.transmitter.snr_db.toFixed(1)} dB ·
          CFO {selftest.transmitter.cfo_hz.toFixed(1)} Hz
        </b>
      </div>
      <p className="verdict-line">
        {selftest.success
          ? 'The sentence came back. Every measurement above is certified by the fact that the code decoded.'
          : 'The sentence did not come back — SHRUTI reports what it measured and declines the rest.'}
      </p>
    </div>
  )
}

export default function App() {
  const { result, busy, stage, error, lang } = useStore()
  const setResult = useStore((s) => s.setResult)
  const setBusy = useStore((s) => s.setBusy)
  const setError = useStore((s) => s.setError)
  const setLang = useStore((s) => s.setLang)
  const [version, setVersion] = useState('')

  useEffect(() => {
    api.health().then((h) => setVersion(h.version)).catch(() => setVersion('offline'))
  }, [])

  const onFile = useCallback(async (f: File) => {
    setBusy(true, `reading ${f.name}`)
    try {
      setResult(await api.analyse(f))
    } catch (e) {
      setError(String(e))
    } finally {
      setBusy(false)
    }
  }, [setBusy, setResult, setError])

  return (
    <div className="app">
      <header>
        <div className="brand">
          <svg className="brand-mark" viewBox="0 0 46 46" fill="none" aria-hidden="true">
            <rect width="46" height="46" rx="12" fill="#e8f4f0" />
            <path d="M10 23h5l3-10 5 21 5-25 3 14h5" stroke="currentColor" strokeWidth="2.3" strokeLinecap="round" strokeLinejoin="round" />
          </svg>
          <div>
            <h1>{t(lang, 'title')}</h1>
            <span className="tag">{t(lang, 'subtitle')}</span>
          </div>
        </div>
        <div className="head-right">
          <span className="ver">v{version}</span>
          <button className="lang" onClick={() => setLang(lang === 'en' ? 'hi' : 'en')}>
            {lang === 'en' ? 'हिन्दी' : 'English'}
          </button>
        </div>
      </header>

      <main>
        <aside>
          <DropZone onFile={onFile} />
          <SelfTestPanel />
          {result && <Capabilities caps={result.capabilities} />}
        </aside>

        <div className="workspace">
          {busy && (
            <div className="busy">
              <div className="spinner" />
              {t(lang, 'analysing')}… {stage}
            </div>
          )}
          {error && <div className="error">{error}</div>}
          {!result && !busy && (
            <div className="empty">
              <svg className="empty-art" viewBox="0 0 380 160" fill="none" aria-hidden="true">
                <rect x="30" y="8" width="320" height="144" rx="12" fill="#f5f9f7" />
                <path d="M54 44h272M54 80h272M54 116h272M90 26v108M140 26v108M190 26v108M240 26v108M290 26v108" stroke="#dfeae6" />
                <path d="M54 80h54l8-9 9 18 10-35 12 53 13-80 15 106 15-91 13 64 12-38 10 20 9-8h92" stroke="#16877a" strokeWidth="2.5" strokeLinecap="round" strokeLinejoin="round" />
                <circle cx="326" cy="80" r="5" fill="#d69848" stroke="white" strokeWidth="2" />
              </svg>
              <h2>{lang === 'en' ? 'Ready for a closer look.' : 'संकेत को करीब से समझें।'}</h2>
              <p>Drop a capture, or press <b>{t(lang, 'runSelfTest')}</b> to run the blind self-test.</p>
            </div>
          )}

          {result && (
            <>
              <SelfTestOutcomeBanner />
              <Verdict res={result} />

              <div className="plots-grid">
                {result.plots?.spectrum && (
                  <figure><figcaption>{t(lang, 'spectrum')}</figcaption>
                    <Spectrum data={result.plots.spectrum} /></figure>
                )}
                {result.plots?.constellation && (
                  <figure><figcaption>{t(lang, 'constellation')}</figcaption>
                    <Constellation data={result.plots.constellation} /></figure>
                )}
                {result.plots?.waterfall && (
                  <figure className="wide"><figcaption>{t(lang, 'waterfall')}</figcaption>
                    <Waterfall data={result.plots.waterfall} /></figure>
                )}
                {result.fieldmap && (
                  <figure className="wide"><figcaption>{t(lang, 'entropy')}</figcaption>
                    <EntropyProfile fieldmap={result.fieldmap} /></figure>
                )}
              </div>

              <div className="panel-grid">
                <ContainerPanel res={result} />
                <Measurements proposals={result.proposals} />
                <WaveformRanking matches={result.matches} />
                {result.fieldmap && <FieldTable fieldmap={result.fieldmap} />}
                <Payload res={result} />
                {result.notes.length > 0 && (
                  <section className="panel">
                    <h3>{t(lang, 'notes')}</h3>
                    <ul className="notes">{result.notes.map((n, i) => <li key={i}>{n}</li>)}</ul>
                  </section>
                )}
              </div>
            </>
          )}
        </div>
      </main>


    </div>
  )
}
