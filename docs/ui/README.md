# Interface screenshots

Captured by [`scripts/capture_ui.py`](../../scripts/capture_ui.py) from the
built interface, at a 1600×1000 viewport (the phone shot at 390×844, 2×). No
engine is needed — the two recorded missions ship inside the bundle. To
regenerate:

```bash
cd frontend && npm run build && cd ..
python scripts/capture_ui.py
```

| File | State |
|---|---|
| `01-landing.jpg` | Landing page |
| `02-missions.jpg` | The mission library, as *Explore a mission* brings it into view |
| `03-pipeline.jpg` | The pipeline, L0 to L8, with the closure feedback |
| `04-decode-sequence.jpg` | A mission's decode sequence, part-way through |
| `05-console.jpg` | Console overview — Mission 01, deep-space telemetry |
| `06-ground-truth.jpg` | What was sent beside what SHRUTI measured |
| `07-signal.jpg` | Spectrum, constellation and waterfall |
| `08-bits.jpg` | Entropy profile, payload and frame structure, one byte selected |
| `09-console-hf.jpg` | Console overview — Mission 02, HF data relay |
| `10-hindi.jpg` | The landing page in Hindi |
| `11-mobile.jpg` | The console on a phone |
