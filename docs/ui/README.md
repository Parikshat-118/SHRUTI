# Interface screenshots

Captured from a live server by [`scripts/capture_ui.py`](../../scripts/capture_ui.py)
at a 1600×1000 viewport, 2× device scale. To regenerate:

```bash
python -m shruti.cli gui --port 8000 &
python scripts/capture_ui.py
```

| File | State |
|---|---|
| `01-empty-state.png` | Landing: drop zone, self-test panel, nothing analysed yet |
| `02-selftest-result.png` | A completed blind self-test — outcome banner and verdict |
| `03-full-analysis.png` | The same analysis, whole page: plots and every panel |
| `04-plots.png` | Spectrum, constellation, waterfall and entropy profile |
| `05-panels.png` | Container, physical layer, waveform ranking, frame structure, payload |
| `06-hindi.png` | The interface in Hindi |
| `07-hold-out.png` | Hold-out mode: the waveform's cartridge removed from the library |

The transmitter is randomised on every run, so the waveform, SNR and carrier
offset differ between captures. That is the point of the self-test, not an
inconsistency between screenshots.
