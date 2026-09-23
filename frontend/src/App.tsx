/**
 * SHRUTI — blind signal exploitation, samples to bits.
 *
 * Two views over one store: the landing page, and the analyst console.  The
 * console works with no engine running, because the two recorded missions ship
 * inside the bundle; the engine is needed only to analyse a new capture.
 */
import { useEffect } from 'react'
import { useStore } from './lib/store'
import { useRoute } from './lib/route'
import { loadIndex } from './lib/missions'
import { refreshEngine } from './lib/engine'
import { Starfield } from './components/Space'
import { Landing } from './components/Landing'
import { Console } from './components/Console'

export default function App() {
  const route = useRoute()
  const setCatalogue = useStore((s) => s.setCatalogue)

  useEffect(() => {
    refreshEngine()
    loadIndex().then(setCatalogue).catch(() => setCatalogue({ cartridges: 0, missions: [] }))
  }, [setCatalogue])

  useEffect(() => {
    if (route.view === 'home') window.scrollTo(0, 0)
  }, [route.view])

  return (
    <>
      <div className={`sky sky-${route.view}`} aria-hidden="true">
        <div className="nebula" />
        <Starfield />
      </div>
      {route.view === 'home' ? <Landing /> : <Console missionId={route.mission} />}
    </>
  )
}
