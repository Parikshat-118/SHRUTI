import { readFileSync } from 'node:fs'
import { defineConfig } from 'vite'
import react from '@vitejs/plugin-react'

const { version } = JSON.parse(readFileSync(new URL('./package.json', import.meta.url), 'utf8'))

// Built output goes straight into the Python package so `shruti gui` serves it
// with no extra step, and so the air-gapped install is one folder copy.
//   base: './'  -> the same bundle works mounted at / (FastAPI) or at a
//                  subpath (GitHub Pages T0) with no rebuild.
export default defineConfig({
  plugins: [react()],
  base: './',
  define: { __APP_VERSION__: JSON.stringify(version) },
  build: {
    outDir: '../shruti/web/static',
    emptyOutDir: true,
    // Everything is inlined or emitted locally: no CDN, no external font, no
    // runtime fetch to anywhere. The no-egress CI job fails the build otherwise.
    assetsInlineLimit: 4096,
  },
  server: {
    proxy: { '/api': 'http://127.0.0.1:8000' },
  },
})
