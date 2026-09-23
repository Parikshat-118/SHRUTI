# Deploying SHRUTI

Every tier below costs **₹0**. They are not alternatives — they serve different
audiences, and which is which matters.

> **Zero cloud is the point.** Intercept data does not go to a third-party
> cloud, free tier or not, region or not. The hosted tiers below exist so that
> new users can *try* the tool without installing anything. The actual
> deliverable is T4: an offline installer for a machine that has never been
> online.

| Tier | Who it is for | What it proves |
|---|---|---|
| T0 · GitHub Pages | Anyone, with nothing installed | Opens on a phone. Zero install, zero trust |
| T1 · Hugging Face Spaces | Public trial | Upload a real file; the full engine runs |
| T2 · Google Cloud Run | The "deploy on Google" path | Same image, production platform |
| T3 · Google Colab | Students, researchers | Run the chain in a browser, no setup |
| **T4 · Offline installer** | **Air-gapped operations. The real product** | Installs with no network at all |
| T5 · Batch over an archive | An agency's existing storage | The highest-value deployment |

---

## T4 · Offline installer — build this first

Everything else falls out of it in an afternoon.

### Option A — Docker tarball

```bash
docker build -t shruti:2.0.0 .
docker save shruti:2.0.0 | gzip > shruti-2.0.0-offline.tar.gz    # ~400 MB
```

On the air-gapped machine:

```bash
docker load < shruti-2.0.0-offline.tar.gz
docker run -p 7860:7860 shruti:2.0.0
```

### Option B — vendored wheelhouse (no Docker, no admin rights)

```bash
mkdir -p dist/wheelhouse
pip download ".[gui]" -d dist/wheelhouse
(cd frontend && npm ci && npm run build)
cp -r shruti cartridges pyproject.toml README.md LICENSE NOTICE dist/
```

Copy `dist/` to a USB stick. On the target:

```bash
pip install --no-index --find-links wheelhouse ".[gui]"
shruti gui
```

**No network. No admin rights. No Python knowledge.** The whole sequence — pull
the network cable, install from the stick, analyse a file — takes about sixty
seconds, which is what makes the offline claim checkable rather than verbal.

### Proving the offline claim

Anyone can *claim* their tool works offline. The engine's `no-egress` check
replaces `socket()` with something that raises, runs the entire pipeline, and
fails the build if anything attempts a connection — *this binary cannot phone
home*, checked on every commit. It joins this repository's CI with the final
release, alongside the decoding core it exercises. Until then, CI already fails
the build if the interface bundle references any external origin.

---

## T1 · Hugging Face Spaces — the public trial link

Free CPU tier, **no credit card**.

1. Create a Space → SDK **Docker** → public.
2. Push this repository to it:

```bash
git remote add space https://huggingface.co/spaces/<user>/shruti
git push space main
```

3. Add a `README.md` header block at the repo root for the Space metadata:

```yaml
---
title: SHRUTI
emoji: 📡
colorFrom: indigo
colorTo: blue
sdk: docker
app_port: 7860
pinned: false
license: apache-2.0
---
```

**Honest limits to state, not hide:** the free tier sleeps after inactivity and
takes ~30 s to wake; CPU only. SHRUTI is CPU-first by design, so nothing is lost
except the cold start.

---

## T2 · Google Cloud Run

Same image. Scale-to-zero, so ₹0 at light traffic (2 M requests/month free).

```bash
gcloud run deploy shruti \
  --source . \
  --region asia-south1 \
  --allow-unauthenticated \
  --memory 2Gi \
  --cpu 2 \
  --timeout 300
```

Requires a GCP account with billing **enabled** — a card on file, though nothing
is charged at this scale. `asia-south1` is Mumbai; keep data in-country.

---

## T0 · GitHub Pages — the static browser build

Pre-computed analyses, fully interactive plots and provenance brushing, no
backend. Opens on any device, including a phone, with nothing installed.

```bash
# 1. Pre-compute a few analyses into static JSON
python scripts/make_static_build.py --out frontend/public/static

# 2. Build with the Pages base path
cd frontend && npm run build

# 3. Publish
git subtree push --prefix shruti/web/static origin gh-pages
```

`vite.config.ts` sets `base: './'`, so the same bundle works mounted at `/`
(FastAPI) or at a subpath (Pages) with no rebuild.

---

## T3 · Colab

`notebooks/SHRUTI_Colab.ipynb` runs the full pipeline **CPU-only**. Limits worth
stating: 12 h session cap, 90 min idle timeout, no guaranteed accelerator — none
of which matter, because nothing here needs a GPU.

---

## T5 · Batch over an archive

The highest-value deployment, and the least obvious one.

```bash
shruti analyse '/archive/**/*.iq' --batch --resume --report /index/
```

One report per capture, resumable, headless. The agency's real asset is the
years of captures nobody has had the hours to open; cross-file consistency and
cross-capture correlation get *strictly better* the more files exist.

**Sensor-side split.** Run L0–L2 on a Raspberry-Pi-class box at the sensor and
forward only what survives detection; run L3–L8 at the analyst's desk. Same
codebase, two configuration profiles, no hardware designed or bought. At one
8 Msps `int16` sensor that is 32 MB/s — 2.76 TB per sensor-day, ~10 PB/year
across ten sensors — reduced roughly 100× by triage at a 1% duty cycle.

---

## What must be in the repository

Each item is a claim a reader can verify without running anything.

- [x] `README.md` answering: what it accepts, how it is structured, how to run it, how you know it works
- [x] `NOTICE` with the full dependency position (licence declared in `pyproject.toml`)
- [x] `Dockerfile` — multi-stage, non-root, healthcheck
- [x] CI: interface build · published engine layers · SBOM · licence audit
- [ ] CI: tests · **no-egress** · docker — with the final release
- [x] `cartridges/` under CC-BY-4.0, separate from the code
- [ ] `tests/` — unit plus the round-trip oracle — with the final release
- [x] `docs/` — architecture and this file
- [x] Screenshots of the GUI in the README (`docs/ui/`, regenerated by `scripts/capture_ui.py`)

**That last one is not decoration.** Most people will not run the code before
deciding whether it is worth their time; they will scroll the README and look at
pictures.
