/** Engine health, polled on load and on demand from the console. */
import * as api from './api'
import { useStore } from './store'

export async function refreshEngine() {
  const { setEngine } = useStore.getState()
  setEngine({ ...useStore.getState().engine, online: null })
  try {
    const h = await api.health()
    setEngine({ online: true, version: h.version, cartridges: h.cartridges })
  } catch {
    setEngine({ online: false, version: '', cartridges: 0 })
  }
}
