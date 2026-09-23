/** Number formatting shared by the tiles, tables and charts. */

export function hz(v: number | null | undefined, digits = 3): string {
  if (v == null || !Number.isFinite(v)) return '—'
  const a = Math.abs(v)
  if (a >= 1e9) return `${(v / 1e9).toFixed(digits)} GHz`
  if (a >= 1e6) return `${(v / 1e6).toFixed(digits)} MHz`
  if (a >= 1e3) return `${(v / 1e3).toFixed(digits)} kHz`
  return `${v.toFixed(1)} Hz`
}

/** Split a value into number and unit so tiles can size them separately. */
export function scaled(v: number | null | undefined, unit: string): [string, string] {
  if (v == null || !Number.isFinite(v)) return ['—', '']
  const a = Math.abs(v)
  if (a >= 1e9) return [(v / 1e9).toFixed(3), `G${unit}`]
  if (a >= 1e6) return [(v / 1e6).toFixed(3), `M${unit}`]
  if (a >= 1e3) return [(v / 1e3).toFixed(3), `k${unit}`]
  return [v.toFixed(1), unit]
}

export function signed(v: number, digits = 1): string {
  return `${v >= 0 ? '+' : '−'}${Math.abs(v).toFixed(digits)}`
}

export function int(v: number | null | undefined): string {
  return v == null ? '—' : Math.round(v).toLocaleString()
}

export function pct(v: number | null | undefined, digits = 1): string {
  return v == null || !Number.isFinite(v) ? '—' : `${(v * 100).toFixed(digits)}%`
}

/** Replace non-printing bytes so a decoded payload never breaks layout. */
export function printable(s: string): string {
  let out = ''
  for (const ch of s) {
    const c = ch.codePointAt(0) ?? 0
    const ok = (c >= 32 && c < 127) || (c >= 160 && c !== 65533)
    out += ok ? ch : '·'
  }
  return out
}
