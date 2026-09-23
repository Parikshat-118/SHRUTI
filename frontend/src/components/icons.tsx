/** Inline line icons — no icon font, nothing fetched. */
import type { SVGProps } from 'react'

type P = SVGProps<SVGSVGElement>

function Svg({ children, ...p }: P) {
  return (
    <svg
      viewBox="0 0 24 24" width="20" height="20" fill="none" stroke="currentColor"
      strokeWidth="1.6" strokeLinecap="round" strokeLinejoin="round" aria-hidden="true" {...p}
    >
      {children}
    </svg>
  )
}

export const Logo = (p: P) => (
  <svg viewBox="0 0 32 32" width="28" height="28" fill="none" aria-hidden="true" {...p}>
    <circle cx="16" cy="16" r="14.5" stroke="currentColor" strokeOpacity=".35" />
    <path d="M4.5 16h4l2.5-6.5 4 13 4-17 3 10.5h5.5" stroke="currentColor" strokeWidth="2" strokeLinecap="round" strokeLinejoin="round" />
    <circle cx="27.5" cy="16" r="2" fill="#ff9a5c" />
  </svg>
)

export const Overview = (p: P) => (
  <Svg {...p}><rect x="3.5" y="3.5" width="7" height="7" rx="2" /><rect x="13.5" y="3.5" width="7" height="7" rx="2" /><rect x="3.5" y="13.5" width="7" height="7" rx="2" /><rect x="13.5" y="13.5" width="7" height="7" rx="2" /></Svg>
)
export const Target = (p: P) => (
  <Svg {...p}><circle cx="12" cy="12" r="8.5" /><circle cx="12" cy="12" r="4.5" /><circle cx="12" cy="12" r="1" fill="currentColor" /></Svg>
)
export const Wave = (p: P) => (
  <Svg {...p}><path d="M2.5 12h2.5l2-6 3 12 3-15 2.5 12 2-6h4" /></Svg>
)
export const Binary = (p: P) => (
  <Svg {...p}><rect x="4" y="4" width="5" height="7" rx="2.5" /><path d="M15 4v7M13.5 5.5 15 4" /><path d="M5.5 13v7M4 14.5 5.5 13" /><rect x="14" y="13" width="5" height="7" rx="2.5" /></Svg>
)
export const Shield = (p: P) => (
  <Svg {...p}><path d="M12 3 4.5 6v5.5c0 4.4 3.1 8.2 7.5 9.5 4.4-1.3 7.5-5.1 7.5-9.5V6L12 3Z" /><path d="m8.8 12.2 2.3 2.3 4.3-4.6" /></Svg>
)
export const Upload = (p: P) => (
  <Svg {...p}><path d="M12 15V4m-4.5 4.5L12 4l4.5 4.5M4 14.5V18a2 2 0 0 0 2 2h12a2 2 0 0 0 2-2v-3.5" /></Svg>
)
export const Globe = (p: P) => (
  <Svg {...p}><circle cx="12" cy="12" r="8.5" /><path d="M3.5 12h17M12 3.5c2.4 2.4 3.6 5.2 3.6 8.5s-1.2 6.1-3.6 8.5c-2.4-2.4-3.6-5.2-3.6-8.5S9.6 5.9 12 3.5Z" /></Svg>
)
export const Exit = (p: P) => (
  <Svg {...p}><path d="M14 4.5h3.5a2 2 0 0 1 2 2v11a2 2 0 0 1-2 2H14" /><path d="M10 16.5 5.5 12 10 7.5M5.5 12H15" /></Svg>
)
export const Hash = (p: P) => (
  <Svg {...p}><path d="M9.5 4 8 20M16 4l-1.5 16M4.5 9h16M3.5 15h16" /></Svg>
)
export const Clock = (p: P) => (
  <Svg {...p}><circle cx="12" cy="12" r="8.5" /><path d="M12 7.5V12l3 2" /></Svg>
)
export const Pulse = (p: P) => (
  <Svg {...p}><path d="M3 12h3.5l1.5-3 2 7 2.5-11 2.5 11 1.5-4H21" /></Svg>
)
export const Compass = (p: P) => (
  <Svg {...p}><circle cx="12" cy="12" r="8.5" /><path d="m15.5 8.5-2 5-5 2 2-5 5-2Z" /></Svg>
)
export const ChevronDown = (p: P) => (
  <Svg {...p}><path d="m7.5 10 4.5 4.5 4.5-4.5" /></Svg>
)
export const ChevronRight = (p: P) => (
  <Svg {...p}><path d="m10 7.5 4.5 4.5-4.5 4.5" /></Svg>
)
export const ArrowRight = (p: P) => (
  <Svg {...p}><path d="M5 12h14m-5.5-5.5L19 12l-5.5 5.5" /></Svg>
)
export const Check = (p: P) => (
  <Svg {...p}><path d="m5.5 12.5 4 4 9-9.5" /></Svg>
)
export const Cross = (p: P) => (
  <Svg {...p}><path d="m7 7 10 10M17 7 7 17" /></Svg>
)
export const Eye = (p: P) => (
  <Svg {...p}><path d="M2.5 12S6 5.5 12 5.5 21.5 12 21.5 12 18 18.5 12 18.5 2.5 12 2.5 12Z" /><circle cx="12" cy="12" r="3" /></Svg>
)
export const Dice = (p: P) => (
  <Svg {...p}><rect x="4" y="4" width="16" height="16" rx="3.5" /><circle cx="9" cy="9" r="1" fill="currentColor" /><circle cx="15" cy="15" r="1" fill="currentColor" /><circle cx="15" cy="9" r="1" fill="currentColor" /><circle cx="9" cy="15" r="1" fill="currentColor" /></Svg>
)
export const Satellite = (p: P) => (
  <Svg {...p}>
    <g transform="rotate(45 12 12)">
      <rect x="9.5" y="9.5" width="5" height="5" rx="1" />
      <rect x="2.5" y="10" width="5" height="4" rx=".5" />
      <rect x="16.5" y="10" width="5" height="4" rx=".5" />
      <path d="M7.5 12h2M14.5 12h2" />
    </g>
    <path d="M5.5 16a3 3 0 0 0 2.5 2.5M3 16.5a6 6 0 0 0 4.5 4.5" />
  </Svg>
)
export const Refresh = (p: P) => (
  <Svg {...p}><path d="M19.5 12a7.5 7.5 0 1 1-2.2-5.3M19.5 4.5v4h-4" /></Svg>
)
