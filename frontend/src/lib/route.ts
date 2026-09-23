/**
 * Hash routing — three routes, no router dependency.
 *
 *     #/                 landing
 *     #/console          the console, with whatever result is loaded
 *     #/mission/<id>     the console, replaying a recorded mission
 *
 * Hash rather than path routing so the same bundle works from FastAPI, from a
 * GitHub Pages subpath and from a file:// copy on an air-gapped laptop.
 */
import { useEffect, useState } from 'react'
import { useStore } from './store'

export type Route =
  | { view: 'home' }
  | { view: 'console'; mission?: string }

export function parse(hash: string): Route {
  const h = hash.replace(/^#\/?/, '')
  if (h.startsWith('mission/')) {
    return { view: 'console', mission: decodeURIComponent(h.slice('mission/'.length)) }
  }
  if (h === 'console') return { view: 'console' }
  return { view: 'home' }
}

export function go(to: string) {
  if (window.location.hash !== to) window.location.hash = to
}

export function useRoute(): Route {
  const [route, setRoute] = useState(() => parse(window.location.hash))
  useEffect(() => {
    const on = () => setRoute(parse(window.location.hash))
    window.addEventListener('hashchange', on)
    return () => window.removeEventListener('hashchange', on)
  }, [])
  return route
}

/**
 * Open a recorded mission.  Asking for the one already on screen replays it,
 * rather than doing nothing — a judge clicking it again wants to see it again.
 */
export function openMission(id: string) {
  const { source, result, setReplaying } = useStore.getState()
  go(`#/mission/${id}`)
  if (result && source?.kind === 'mission' && source.id === id) {
    window.scrollTo(0, 0)
    if (!window.matchMedia?.('(prefers-reduced-motion: reduce)').matches) setReplaying(true)
  }
}
