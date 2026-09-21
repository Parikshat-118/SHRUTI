# SHRUTI v2 — Closing the Loop to Bits

**SIH 2026 · Problem Statement SIH26147 · NTRO**
*Revision of [SHRUTI-SIH26147.md](SHRUTI-SIH26147.md) against the **official** problem statement text*

| Field | Value |
|---|---|
| Category / Theme | **Software** · Space Technology — see §17.2 (the deliverable is a program that reads a file) and §4.8 (the theme tag is a clue, not an accident) |
| Supersedes | SHRUTI v1 (4 September 2026) |
| Trigger for revision | Official PS text obtained — materially different from the catalogue title v1 was written against |
| Document status | Working design doc, v2 — **Part I** (technical) + **Part II** (shipping) |
| Last updated | 18 September 2026 · Part II added |
| Verdict on v1 | **Right thesis. Wrong scope. Roughly 40% coverage of the official requirements.** |
| Verdict on Part I | **Right architecture. No shipping case.** Excellent on novelty and complexity; near-silent on feasibility, sustainability, deployment, cost and scale of impact — five of the nine things SIH actually scores. §15 onward fixes that. |

> `śruti` (श्रुति) — that which is heard.
> `artha` (अर्थ) — its meaning.
>
> v1 built the ear. v2 adds the part that understands what was said. The official PS demands both,
> and the second half is where the idea stops being clever and becomes unbeatable.

---

# PART I — Why it is right

## 0 · The verdict, in six lines

1. **v1's central reframe — blind analysis as an inverse problem, verified by resynthesis — is correct and still the winning idea.** Do not abandon it.
2. **v1 stops at the physical layer. The official PS does not.** It explicitly requires de-interleaving, four families of FEC decoding, and bitstream correlation to find header and payload. v1 delivers none of these and *brags* about handing them off.
3. **One v1 design decision is now actively wrong:** §5/L4's "symbol sequence is a nuisance parameter — do not try to recover the data bits."
4. **The fix is not a bolt-on. It is a thesis upgrade that makes the physical layer better.** Error-correcting redundancy is the most precise measuring instrument in the entire signal, and every competing team will treat it as an obstacle instead of an instrument.
5. **The novelty claim survives and sharpens.** Two mature literatures sit adjacent and never touch. §5 states the gap precisely, with sources.
6. **And then Part II, added later:** all of the above is the argument that SHRUTI is *right*. It is not the argument that it can be *built*, *deployed* and *maintained* — which is most of what a government hackathon actually scores. **§15–§24.**

---

## 1 · What the official text actually asks for, versus what v1 built

The catalogue title v1 worked from — *"automated analysis of .IQ/.wav signal files with blind parameter
extraction"* — reads as a physical-layer problem. The official text is not a physical-layer problem.
It is a **blind exploitation chain, end to end, from raw samples to segmented header and payload.**

Read the operative sentence in the Background again:

> *"This data is often insufficient for fine grain analysis for parameter extraction such as modulation
> type, sampling rate, **FEC, interleaving**, etc."*

FEC and interleaving are named in the *Background*, in the *Description*, and as two of the five
enumerated GUI features. This is not an optional stretch goal. It is half the problem statement.

### 1.1 Scorecard — v1 against the five official requirements

| # | Official requirement | v1 coverage | Gap |
|---|---|---|---|
| i | Identify signal parameters (sampling frequency, modulation, **FEC**, **interleaving**) | **Partial** | Sampling frequency and modulation: excellent (L0, L3, L4). FEC and interleaving: **absent entirely** |
| ii | Demodulate signals (FSK, QAM, PSK) | **No** | v1 *fits* a modulation hypothesis; it never produces symbols or bits. "Fitting" ≠ "demodulating" and a judge will make that distinction |
| iii | De-interleaving (block, convolutional, diagonal, pseudo-random) | **No** | Not mentioned anywhere in v1 |
| iv | FEC (short-constraint convolutional + Viterbi, RS, concatenated, LDPC) | **No** | v1 §3.5 explicitly *hands this off*: "our SigMF output is the input your 2023 FEC problem statement needed" |
| v | Bitstream correlation → header/payload identification | **No** | Requires bits. v1 has no bits |
| — | GUI: spectrum, **constellation plot**, **waterfall**, feature visibility | **Under-weighted** | v1 §8 anti-pattern 4 calls the UI "~10% of the score" and recommends static HTML. The official text says *"GUI based model"* and *"improve feature visibility of signals with the help of GUI"* — the GUI is a named deliverable, not decoration |
| — | HF / VHF / UHF specifically | **Unaddressed** | v1's channel block is generic. HF means ionospheric multipath and Doppler spread, and .wav means audio-band SSB output, not complex IQ |
| — | "Recorded from different sensors and different locations, the parameters may vary" | **Unaddressed** | The PS is pointing at multi-sensor reconciliation. Nobody will notice this line |
| — | "Spectral relationship from training data containing both .IQ and .wav formats" | **Unaddressed** | An explicit invitation to cross-format modelling |

**Two of eleven rows are green.** That is the loophole, and it is worth more attention than every
other criticism in this document combined: v1 is an excellent answer to a problem statement that
NTRO did not write.

### 1.2 Why this happened, and why it is good news

v1 §3.5 got the lineage exactly right and then drew one wrong conclusion. It observed that NTRO's
SIH1447 (2023) asked for **FEC recovery from already-demodulated bits**, and that SIH26147 asks for
the stage *before* it — and concluded the two are complementary problems with a clean handoff.

They are not complementary. **SIH26147 is the union.** NTRO tried the back half in 2023, tried the
front half separately, and has now asked one team for the whole chain in one tool. The 2026 text
names FEC and interleaving explicitly *because the 2023 attempt did not produce something deployable
on real captures.*

That is good news, because it means the winning submission is the one that closes the chain — and
closing the chain is where a genuinely new technical idea lives.

---

## 2 · The thesis upgrade — redundancy is measurement

v1's thesis: *don't label the samples, recover the machine that made them.* Keep it. Extend it.

The PS's Background makes a claim, and every team will accept it without examining it:

> *"This data is often insufficient for fine grain analysis for parameter extraction."*

**It isn't insufficient. Half of it is redundancy, and the analyst is throwing the redundancy away.**

A rate-½ code means that half the bits you received are an exact algebraic constraint on the other
half. Those constraints are not just a route to the payload — they are thousands of independent,
noise-free tests of whether *everything upstream* was estimated correctly. Symbol rate, carrier
offset, timing, pulse shape, spectral inversion, channel taps, even your own receiver's imbalance.
Get any of them slightly wrong and the constraints fail. Get them right and they all hold at once.

This inverts the conventional relationship between the layers:

| Conventional cascade | SHRUTI v2 |
|---|---|
| FEC is the last obstacle before the payload | FEC is the **highest-precision instrument in the system** |
| Information flows samples → params → symbols → bits | Information flows **both ways**; decode success corrects the physical layer |
| Decoding fails ⇒ give up | Decoding fails ⇒ **you have learned which estimate is wrong, and by roughly how much** |
| Confidence is a softmax, or a residual in dB | Confidence is a **binomial test on satisfied parity checks** with a p-value that can reach 10⁻³⁰ |

### 2.1 The precision argument, quantified

A cyclostationary symbol-rate estimator on a short burst delivers perhaps 10⁻⁴–10⁻⁵ relative
accuracy, and at high SNR it hits a self-noise floor set by the unknown payload.

Now demand that an open-loop fit stay symbol-aligned across a whole codeword. Cumulative timing slip
must stay below roughly a tenth of a symbol over *N* symbols, so

```
|ΔRs / Rs|  <  0.1 / N
```

At N = 10⁵ symbols that is **10⁻⁶ — an order of magnitude past what the spectral estimator gave
you**, and it is *certified*, not asserted: the code either decoded or it didn't.

This is not a hopeful analogy. It is the known result behind code-aided synchronisation: the
Cramér–Rao bound for a *coded* transmission sits strictly below the non-data-aided bound and moves
toward the data-aided bound, because the code removes the payload's nuisance uncertainty
([Herzet et al., EURASIP JASP 2005](https://link.springer.com/article/10.1155/ASP.2005.972)).

The pitch line, and it is the best one in either document:

> **"We were never given the transmitter's training sequence. So we built one out of its
> error-correcting code."**

### 2.2 And it works on encrypted traffic

v1 sold payload-invariance as a virtue: *the method works on encrypted traffic.* Keep the virtue,
and notice it survives the upgrade intact — because in the overwhelming majority of real systems the
order is

```
plaintext → encrypt → frame → FEC encode → scramble → interleave → modulate
```

**Encryption sits inside the FEC, not outside it.** So on an encrypted emitter you still recover the
frame period, the header fields, the interleaver depth, the code rate, the generator polynomials, the
scrambler, and the ciphertext bits — plus an entropy measurement that *demonstrates* it is encrypted
rather than merely coded. For NTRO that is a complete technical exploitation report on a link nobody
can read, which is exactly the product they want.

---

## 3 · The loopholes — fifteen of them, with fixes

Ordered by how much damage each one does if a judge finds it before you admit it.

| # | Loophole | Severity | Fix (detail below) |
|---|---|---|---|
| 1 | Three of five official requirements not addressed | **Fatal** | §4 ARTHA layers L5–L7 |
| 2 | "Do not recover the data bits" contradicts requirement (v) | **Fatal** | Split the objective: payload-invariant for *search*, payload-recovering for *verification* |
| 3 | "GUI is ~10% and can be static HTML" contradicts the official text | **High** | GUI is a named deliverable; §4 L8 and §7 |
| 4 | UNKNOWN verdict thresholded on residual in dB — not scale-free, not calibrated across SNR | **High** | Goodness-of-fit statistic with a distribution and a p-value, plus a model-error floor |
| 5 | Error bars from per-parameter curvature — wrong when parameters are correlated | **High** | Invert the **full** Fisher information matrix; publish the covariance, not just σ |
| 6 | Parameter degeneracy (roll-off ↔ symbol rate ↔ SNR) unacknowledged | **High** | Cyclic-domain constraints break it; report correlations; standards-lattice prior (§4 L4b) |
| 7 | L1 receiver self-model requires a terminated reference capture — impossible for archived third-party files | **High** | Reference-free artefact tests + cross-file consistency (§4 L1) |
| 8 | Absolute sampling frequency is **not identifiable** from a headerless file. v1 promises it | **High** | State the limit; then solve it by in-band anchoring (§4 L0b) — this becomes a differentiator |
| 9 | HF/VHF/UHF named in the PS; twin has no ionospheric channel | Medium | Watterson / ITU-R F.1487 block, with delay and Doppler spread as recovered parameters |
| 10 | `.wav` treated as a container variant. Real HF `.wav` is **real-valued SSB audio**, possibly spectrally inverted | Medium | Dedicated audio-baseband path + blind inversion resolution (§4 L0c) |
| 11 | "Twin contains impairments, so real captures fit *better*" — asserted, not measured | Medium | Convert to a measurement: publish the real-vs-synthetic residual distribution |
| 12 | Proposal network trained only on twin output shares the twin's model error — residual test cannot catch a correlated failure | Medium | Independent classical proposals (v1 has this) + a real-capture twin-adequacy test |
| 13 | "0.3–3 s per burst" asserted with no basis, and bit-layer work is far heavier | Medium | Anytime/progressive architecture with a stated budget per tier |
| 14 | No minimum-data statement. Interleaver and FEC recovery need ~10⁴–10⁶ bits; a short burst can never yield them | Medium | Per-capability data-sufficiency gate, surfaced in the UI and in the capability envelope |
| 15 | Several v1 citations postdate ordinary verification; incumbents named in §10.1 are the **wrong** incumbents | Medium | §7.5 — **audit completed 18 Sep 2026; two citations were wrong and are corrected.** Incumbents corrected in §8 |

### 3.1 · Loopholes 1 and 2 — the scope hole and the contradiction

v1 §5/L4 says, as a deliberate design choice:

> *"Symbol sequence is a nuisance parameter. Do not try to recover the data bits. Match on statistics
> that are invariant to the payload."*

For the **search** stage that is exactly right, and it must stay: a payload-invariant loss is smooth,
cheap and keeps the optimiser out of a combinatorial hole. But once the search converges, refusing to
go to bits throws away requirement (v) *and* the precision argument of §2.1.

**The fix is a two-regime objective, and the regime boundary is the interesting engineering:**

| Regime | Objective | Symbols treated as | Purpose |
|---|---|---|---|
| **Search** | multi-resolution spectrogram + cyclic-spectrum + envelope distance | Unknown, marginalised out | Get inside the right basin cheaply. v1's L4, unchanged |
| **Lock** | soft-symbol log-likelihood with per-symbol soft decisions | Estimated, soft | Refine to data-aided-class precision |
| **Verify** | code-constraint likelihood — parity checks on soft bits | Determined by the code | Certify, and produce the payload |

The transition rule is itself a defensible contribution: switch from Search to Lock when the residual
stops improving and the constellation's soft-decision entropy drops below a threshold; switch from
Lock to Verify when a candidate code hypothesis reaches a syndrome bias significant at the corrected
level. Every transition is measurable, so the pipeline can explain *where* it stopped and why.

### 3.2 · Loophole 4 — the UNKNOWN threshold is the weakest technical claim in v1

v1 reports `shruti:residual_db: -22.8` and declares IDENTIFIED. Two failure modes:

- **At low SNR** every hypothesis has a large residual, so the threshold rejects correct fits.
- **At high SNR** an arbitrarily small unmodelled impairment produces a residual that dwarfs the
  noise, so the threshold rejects correct fits *again*, for the opposite reason.

A dB threshold cannot be right at both ends. Replace it with a statistic that has a distribution:

```
Normalise the residual by the noise variance the fit itself estimated.
Under a correct model, residual energy / σ̂²  ~  χ²(ν)  with ν set by
sample count minus fitted degrees of freedom.
Report the goodness-of-fit p-value. Add a model-error floor term ε² so that
high-SNR captures are tested against "noise + acknowledged model error",
not against "noise alone".
```

Now the verdict reads `GoF p = 0.31 — residual consistent with noise` instead of `−22.8 dB, trust us`,
and the UNKNOWN decision has a stated false-rejection rate. This is the same upgrade v1 already made
for detection when it chose OS-CFAR over a magic threshold — apply the same discipline one layer up.

**Then test the residual for *structure*, not only for size.** A small but structured residual is
worse than a larger white one. Run a whiteness test and a cyclostationarity scan on the residual. That
single addition produces two new capabilities, in §5.

### 3.3 · Loophole 8 — the sampling-frequency claim, and how to turn it into a win

Requirement (i) asks for the sampling frequency. v1 promises "ranked candidates with evidence." Both
skip a hard fact that a knowledgeable judge will raise:

> **From a headerless sample file, the absolute sampling frequency is not identifiable. Full stop.**
> Every measurable quantity is a *ratio* — cycles per sample, symbols per sample. Multiply the
> assumed rate by 1.7 and every derived number scales by 1.7 while the file remains perfectly
> self-consistent. No amount of processing recovers absolute Hz from the samples alone.

Say this out loud. It costs nothing and it immediately separates you from every team that quietly
prints a number. Then solve it three ways, and the third is the differentiator:

1. **Sidecar and header metadata.** `.sigmf-meta`; the `auxi` RIFF chunk that SDR recorders write into
   `.wav` files, carrying centre frequency and start time ([example implementation](https://github.com/roseengineering/rfsoapyfile));
   RIFF `LIST/INFO`; and the filename conventions of the common recorders (`SDRSharp_YYYYMMDD_HHMMSSZ_<freq>Hz_IQ.wav`,
   `gqrx_YYYYMMDD_HHMMSS_<freq>_<rate>_fc.raw`, HDSDR, SDRuno, SDRangel, KiwiSDR). Unglamorous, and it
   resolves a large fraction of real files for free.
2. **Sensor provenance.** The PS says files come from *different sensors and different locations*. Learn
   each sensor's habits from its archive: a sensor that has produced 8 Msps `int16` files a thousand
   times is a strong prior on the next unlabelled one.
3. **In-band anchoring — the part nobody will do.** If the capture contains *anything* whose parameters
   are standardised, you can solve for the true sample rate from it and every other measurement in the
   file becomes absolute. Candidate anchors, in decreasing reliability:
   - a channel raster: detected emitter spacings that snap to integer multiples of 12.5 kHz or 25 kHz
     under one candidate rate and to nothing under the others;
   - a broadcast pilot (19 kHz FM stereo pilot), a known beacon, an ALE tone set at 375 Hz spacing;
   - standardised symbol rates: real transmitters run at 75, 150, 300, 600, 1200, 2400, 4800, 9600 Bd,
     not at 2377.4;
   - in an audio `.wav`, mains hum at 50 Hz and its harmonics — a free clock reference, when present.

   Anchoring turns a ranked guess into a solved quantity **with a stated basis**, and the evidence
   string that goes in the report — *"sample rate 8.000 Msps, solved from a 25 kHz channel raster across
   six detections, residual 0.4 ppm"* — is the single most analyst-shaped sentence either document
   contains.

### 3.4 · Loophole 7 — artefact rejection without a reference capture

v1's L1 fits the receiver's signature from a capture taken with the input terminated. For files that
arrive from *different sensors and different locations* — i.e. every real file — you will never have
one. Four reference-free tests, all cheap:

| Test | Method | Catches |
|---|---|---|
| DC / LO self-mix | Energy confined to bin 0 with no measurable bandwidth | DC spike, LO leakage |
| Conjugate correlation | Correlate the spectrum with its own conjugate mirror about DC. An I/Q-imbalance image is the conjugate of its twin, so the correlation is high — and the same statistic **estimates the imbalance so you can correct it blindly** | Mirror images |
| Spacing GCD | Take detected tone frequencies, compute the GCD of their spacings. A clock comb has one; independent emitters do not | Spur combs, ADC harmonics |
| Superlinear scaling | Energy at 2f, 3f that grows faster than linearly with the power at f, across time | Front-end nonlinearity products |
| **Cross-file consistency** | A feature at the *same baseband offset* across many files from one sensor, regardless of tuned frequency, is the receiver. An emitter would not follow the tuning | Everything above, retroactively, over an archive |

The last row is new, needs no extra hardware, and gets *stronger* the more files you process — which
makes it a natural pitch for an agency sitting on an archive.

### 3.5 · Loophole 10 — what an HF `.wav` file actually is

v1 treats `.wav` as a container variant of `.IQ`. For HF work it usually isn't. The common case is the
**audio output of an SSB receiver**: real-valued, 8/11.025/22.05/48 kHz, carrying a modem occupying
roughly 300–3400 Hz, typically centred near 1500–1800 Hz. The consequences are specific:

- **There is no complex baseband.** You must form an analytic signal and locate the modem inside the
  audio band. The occupied bandwidth in the file tells you nothing about RF bandwidth directly.
- **The RF centre frequency is gone** unless a sidecar or the filename preserved it. Report it as
  unknown rather than inventing it.
- **The sideband may be inverted.** LSB reception mirrors the spectrum relative to USB, and for a
  symmetric PSK spectrum the magnitude spectrum cannot tell you which. Everything downstream breaks
  silently on the wrong choice.

That last point is the neat one, because §2 already solved it: **try both, and let the decoder decide.**
Spectral inversion is a one-bit hypothesis; the code either satisfies its parity checks or it doesn't.
Where a conventional tool needs a human to flip a switch and listen, SHRUTI resolves it with a
binomial test. Same for the differential-encoding and rotational ambiguities that plague blind PSK.

And two-channel `.wav` genuinely *is* IQ in many recorders (I in left, Q in right) — so the container
inference in L0 must decide between "stereo audio", "IQ-in-stereo" and "mono SSB audio", which the
Hermitian-symmetry and inter-channel-correlation tests settle cheaply.

### 3.6 · Loophole 14 — say how much data each capability needs

Nothing in v1 states data requirements, and the bit layer changes the picture completely:

| Capability | Rough data requirement | Consequence |
|---|---|---|
| Detection, bandwidth, centre | 10³–10⁴ samples | Works on almost any burst |
| Symbol rate, roll-off, modulation family | 10²–10³ symbols | Works on most bursts |
| Frame period / sync word | 10³–10⁴ bits | Needs a sustained transmission |
| Convolutional code reconstruction | 10⁴–10⁵ bits | Needs a sustained transmission |
| Interleaver period and depth | 10⁴–10⁶ bits | Long captures only |
| Pseudo-random interleaver permutation | Not blindly recoverable in general — see §4/L6 | Library match, or honest refusal |

Surface this as a **gate in the UI**, not a footnote: *"burst holds 3.1 kbit; interleaver
reconstruction requires ≥ 20 kbit — capability disabled, reason shown."* Every team that skips this
will attempt FEC identification on a 4 ms burst during their demo and produce confident nonsense.

---

## 4 · Revised architecture — nine layers

v1's L0–L6 stand, with the corrections above folded in. New layers are marked **NEW**. The bit-layer
group L5–L7 is the **ARTHA** engine — *artha*, meaning; and as a backronym, **A**nalysis by
**R**ound-**T**rip **H**ypothesis **A**ttestation.

```
L0  container + format inference          ← + audio-baseband path, in-band rate anchoring
L1  receiver self-model                   ← + reference-free tests, cross-file consistency
L2  wideband detection + emitter tracking
L3  proposal short-list (classical + net)
L4  differentiable twin inversion         ← + HF Watterson channel, standards-lattice prior
L4b iterative emitter peeling             NEW
L5  soft demodulation + descrambling      NEW
L6  interleaver + FEC reconstruction      NEW  ← requirements (iii) and (iv)
L7  bitstream structure + correlation     NEW  ← requirement (v)
L8  GUI, SigMF output, evidence sheet     ← promoted from "10%" to a named deliverable
             ▲                                            │
             └──────────── closure feedback ──────────────┘
                  decode outcome refines L4 parameters
```

The feedback arrow is the whole idea. Everything else is competent engineering.

### 4.1 · L4 additions

**An HF channel that is actually an HF channel.** The PS names HF first. Model it with the standard
Watterson tapped-delay-line and the ITU-R F.1487 good/moderate/poor conditions
([ITU-R F.1487](https://www.itu.int/dms_pubrec/itu-r/rec/f/R-REC-F.1487-0-200005-I!!PDF-E.pdf),
[reference implementation notes](https://www.mathworks.com/help/comm/ug/hf-ionospheric-channel-models.html)),
with delay spread and Doppler spread as **recovered** parameters rather than fixed settings.

Two payoffs. First, without it, a fading HF capture produces a large residual and SHRUTI wrongly
announces UNKNOWN — the honesty mechanism misfires on the PS's primary band. Second, once delay and
Doppler spread are recovered they are *intelligence in their own right*: a propagation-mode hypothesis
(groundwave vs single-hop vs multi-hop skywave) with uncertainty attached, from the same fit that
produced the modulation. State it as a hypothesis, not a range-finder — inferring path length needs
ionospheric assumptions you cannot verify from one receiver — but even as a hypothesis, no competing
submission will produce it.

**The standards-lattice prior — real transmitters are built by humans to specifications.** The
parameter space is not a continuum. Symbol rates cluster on round numbers, roll-offs on 0.2/0.25/0.35/0.5,
channel spacings on 12.5/25 kHz, HF modems on documented configurations. After continuous inversion,
test the estimate against the lattice of standardised values:

- **it snaps within its error bar** ⇒ snap it, report *"consistent with the standard value 2400 Bd
  (1.2σ)"*, and gain precision for free from a prior that is physically justified rather than
  hand-tuned;
- **it snaps to a full system signature** ⇒ report the *system*, not the modulation. An analyst does not
  want "8-PSK"; they want *"consistent with a MIL-STD-188-110 serial waveform, 2400 Bd, 1800 Hz centre"*.
  Build the signature library from open sources — [sigidwiki](http://sigidwiki.com/wiki/Database) alone
  documents 591 signals with parameters and waterfall references;
- **it snaps to nothing** ⇒ that is itself a finding. **Non-conformance is a detection signal:** a
  bespoke, deliberately non-standard, or improvised emitter. Report *"no standard match; closest is X at
  Δ log-likelihood 14.2; parameters follow"*.

This is the bridge from "parameters" to the answer an analyst actually needs, and it is how the
commercial incumbents in §6 frame their own output.

### 4.2 · L4b · Iterative emitter peeling — **NEW**

Only a tool that can *synthesise* can do this, which is why it is unavailable to every classifier-based
team:

1. Fit and invert the strongest emitter.
2. Subtract its reconstruction from the observed samples.
3. Re-run L2 detection on the residual.
4. Repeat until the residual passes the whiteness test of §3.2.

This is CLEAN from radio astronomy, and successive interference cancellation from comms, applied to
blind analysis. It recovers **weak emitters buried under strong ones and signals overlapping in both
time and frequency** — the case the PS implies by asking for whole files rather than pre-channelised
bursts, and the case v1 §8 anti-pattern 2 correctly identifies as decisive but never actually solves.

Report the peeling order and the residual after each stage. It is a compelling live visual: the
spectrogram getting quieter, one emitter at a time, until only noise remains.

### 4.3 · L5 · Soft demodulation and descrambling — **NEW** · requirement (ii)

Requirement (ii) says *demodulate*, and it means it. Once L4 has locked, produce **soft bits**, not hard
ones — per-bit log-likelihood ratios. Everything in L6 works dramatically better on soft information
and this single choice is where most teams will lose their FEC stage.

- Matched filtering, timing interpolation, carrier and phase tracking, equalisation for the HF case.
- FSK, PSK (BPSK/QPSK/8-PSK/π-4-DQPSK), QAM (16/32/64), plus differential variants.
- Resolve the standing ambiguities — phase rotation by π/2 multiples, differential vs absolute
  encoding, bit-order and Gray-mapping conventions, spectral inversion. **All of them are one-bit or
  small-cardinality hypotheses, and all are resolved the same way: by which one lets the code decode.**

**Then descramble — the layer the PS forgot.** Nearly every real military and commercial waveform applies
an additive or self-synchronous scrambler between FEC and modulation. A team that implements FEC and
interleaving but not descrambling will find its FEC stage failing on every real capture for reasons it
cannot diagnose. Blind scrambler recovery is a solved problem in the literature
([self-synchronous scrambler estimation via orthogonal complement space, IEEE Xplore 9802104](https://ieeexplore.ieee.org/document/9802104/)),
and the PS explicitly invites *"additional features if feasible"* — so this is a scored bonus that
nobody else will claim, wrapped around a defect that would otherwise sink them.

### 4.4 · L6 · Interleaver and FEC reconstruction — **NEW** · requirements (iii) and (iv)

This is the layer that answers half the problem statement, and it rests on one structural fact worth
saying on stage because it makes the problem tractable:

> **An interleaver is a permutation, a permutation is linear over GF(2), and a linear code composed with
> a permutation is still a linear code.** So the interleaver-and-FEC composite is one linear map, and its
> dual space — the set of parity checks that hold on the received stream — is recoverable by linear
> algebra on the bits. You do not need to separate the two in order to *detect* them.

Which gives a three-track design:

| Track | Method | Covers | Honest limit |
|---|---|---|---|
| **A · Library match** | Test the stream against a library of standardised parity-check matrices and interleaver specifications — CCSDS, DVB, 3GPP, 802.11n, the documented HF modems | The overwhelming majority of real traffic. Fast, and confidence is decisive | Only finds what is in the library |
| **B · Algebraic reconstruction** | Rank-deficiency and dual-code search over candidate (n, k, period), extended to noise by the "almost rank" criterion ([Sicot & Houcke, ICASSP 2005](https://unpaywall.org/10.1109%2FICASSP.2005.1415838); [Marazin et al., EURASIP JWCN 2011](https://jwcn-eurasipjournals.springeropen.com/counter/pdf/10.1186/1687-1499-2011-168); [interleaved convolutional codes](https://arxiv.org/html/1501.03715v1); [KS-test interleaver estimation, Sensors 2021](https://www.mdpi.com/1424-8220/21/10/3458/htm)) | Unknown and bespoke short-constraint convolutional codes, block interleavers, RS and linear block codes | Needs 10⁴–10⁶ bits (§3.6) |
| **C · Soft-syndrome test** | **The v2 contribution.** Rank methods need hard bits and degrade fast with bit errors. Instead evaluate each candidate parity check on *soft* bits and test the syndrome's bias against the null p = 0.5 with a binomial test, Bonferroni- or FDR-corrected across the hypothesis grid | Extends B several dB down in SNR — and yields a **p-value instead of a threshold** | Costs a hypothesis sweep |

**Cover all four interleaver types the PS names, by name.** Requirement (iii) enumerates *Block,
Convolution, Diagonal, Pseudo Random*, and Part I's track table only speaks to block and pseudo-random. A
judge holding the PS will check this list item by item, so answer it item by item:

| Type the PS names | Structure | Blind signature | Track |
|---|---|---|---|
| **Block** | Write rows, read columns, over an *R × C* frame | Syndrome failures periodic at *R·C*; the composite linear map has a rank deficiency at that period | A and B, solved |
| **Convolutional** (Ramsey/Forney) | A bank of *N* shift registers with delays 0, *M*, 2*M*, … — **no frame boundary at all** | Period *N*, and the delay increment *M* shows as a *staircase* rather than a block in the syndrome-failure pattern. The absence of a frame boundary is itself the discriminator from block | A and B — **and the "no frame boundary" test is what tells the two apart, which is the part to state on stage** |
| **Diagonal** | A block interleaver read along diagonals — one specific permutation of the *R × C* grid | Same period as block, different residual pattern within the period | A (enumerate the diagonal variants alongside the block ones — it is a small, finite family, not an open problem) |
| **Pseudo-random** | An arbitrary permutation from a generator | Period detectable; permutation **not** blindly recoverable in general — below | Detect and bound only. Honest refusal |

The unifying point, and it is the one worth making: **all four are permutations, all four are therefore linear
over GF(2), and the §4.4 opening argument covers all four identically for *detection*.** What differs between
them is only the *pattern* of syndrome failures, which is cheap to classify once the composite is detected.
So requirement (iii) is four named cases of one mechanism, not four separate engineering efforts — say that,
and the requirement stops looking like a wall.

**On pseudo-random interleavers, be honest and be specific.** An unknown pseudo-random permutation of
large period is not blindly recoverable in the general case. Say so — it is the one place in this
problem where the mathematics genuinely refuses. Then state precisely what *is* achievable, because it
is a great deal: **detect that an interleaver is present, and estimate its period and depth** from the
periodicity of syndrome-failure positions, even when the permutation itself stays out of reach. A tool
that reports *"interleaved, period 1152, depth unrecoverable — permutation not blindly identifiable at
this length"* is more valuable than one that guesses, and infinitely more valuable than one that
crashes.

Concatenated codes fall out of the same machinery applied twice — an outer RS and an inner
convolutional code, in the classic arrangement the PS names — with the inner code identified first,
decoded, and the outer code identified on the decoder's output.

### 4.5 · Keeping L6 differentiable — why the closure loop is buildable

The objection a strong judge will raise: *Viterbi and syndrome checks are discrete. How do you
back-propagate a symbol-rate gradient through a decoder?* The answer is that the soft-output versions of
these decoders are already differentiable, and this is established engineering rather than a hope:

| Component | Differentiable form | Precedent |
|---|---|---|
| De-interleaving | A gather under a fixed permutation | Trivially differentiable |
| Convolutional / RS trellis | **BCJR forward–backward**, the same algorithm family as HMM/CTC forward–backward | Learned/differentiable BCJR is established — [BCJRNet: Data-Driven Factor Graphs for Deep Symbol Detection (arXiv 2002.00758)](https://arxiv.org/abs/2002.00758); [neural RSC decoding in Communication Algorithms via Deep Learning (arXiv 1805.09317)](https://arxiv.org/abs/1805.09317) |
| LDPC | **Belief propagation unrolled as a network**, damped or weighted | Neural BP is a mature line of work — [Nachmani et al., Learning to Decode Linear Codes Using Deep Learning (arXiv 1607.04793)](https://arxiv.org/abs/1607.04793) is the foundational weighted-BP-as-a-network result; extended in [arXiv 1706.07043](https://arxiv.org/abs/1706.07043), with [training recipes (arXiv 2205.00481)](https://arxiv.org/abs/2205.00481) |
| Code / interleaver *structure* | Enumerated, not descended | Same discrete/continuous split v1 already uses for modulation |

So the objective

```
L(θ)  =  − log p( observed samples | θ_PHY , H_code , π_interleaver )
```

is differentiable in every continuous parameter θ_PHY, with the discrete structure `(H, π)` enumerated
over the L6 short-list. Gradient descent on the *code's own likelihood* with respect to the *symbol
rate* is the mechanism, and it is the sentence to put on the slide.

If it does not converge in time, §11's descope ladder keeps every demo moment intact — the loop is the
ceiling, not the floor.

### 4.6 · L7 · Bitstream structure and correlation — **NEW** · requirement (v)

The PS's final requirement, and it wants *header and payload identification*. Four steps, all classical,
all cheap once you have bits:

1. **Frame period detection.** Autocorrelate the bitstream at all lags; a periodic sync word produces a
   comb of peaks. Cross-check with cumulative-filtering methods for sync-word recovery
   ([self-correlation approach](https://www.mdpi.com/2078-2489/10/2/64), [joint frame sync and encoder ID for LDPC](https://www.researchgate.net/publication/271481253_Joint_blind_frame_synchronization_and_encoder_identification_for_LDPC_codes)).
2. **Reshape and profile.** Fold the stream into a matrix at the detected frame length and compute
   per-column entropy. **Low-entropy columns are sync words, addresses, static fields and padding;
   high-entropy columns are payload.** The entropy profile across one frame *is* the header/payload
   segmentation, produced automatically, and it plots as a single readable figure.
3. **Field typing.** Columns that increment monotonically are counters or sequence numbers; columns that
   change only between transmissions are addresses or session identifiers; a trailing block whose
   entropy is a near-perfect 1.0 bit/bit is **encrypted or compressed** — and saying which, with a
   measured number attached, is a genuine intelligence product.
4. **Cross-capture correlation.** The PS's phrase supports a second reading worth taking: correlate
   recovered bitstreams *between* captures. Matching streams across two sensors prove a common
   transmission; matching headers across time prove network membership or retransmission. This is traffic
   analysis, it needs no new machinery, and it is what an agency with an archive actually wants.

Requirement (v) is the cheapest of the five to satisfy well and the one most teams will never reach,
because reaching it requires having succeeded at (ii), (iii) and (iv) first.

### 4.7 · L8 · The GUI, correctly weighted — and one idea worth the whole panel

v1 §8 anti-pattern 4 is right that teams over-invest in dashboards and under-invest in engines. But
against the official text it is a scoring error: *"The GUI based model will have features to…"* and
*"improve feature visibility of signals with the help of GUI"* make the interface a named deliverable,
and the PS enumerates the views it expects — spectrum, **constellation plot**, **waterfall**. Build the
engine first, then build a real GUI, and budget for it.

Structure it around the analyst's workflow rather than as a wall of charts: **triage → drill → decode →
export.** Then add the one element that no other team can build, because it requires having modelled the
entire chain:

> **Provenance brushing.** Every layer is linked to every other. Click a suspected header field in the
> bitstream view and the exact symbols that carried it light up in the constellation, the exact samples
> light up in the waterfall, and the exact microseconds highlight on the time axis. Drag a box on the
> spectrogram and see which bits came from it.

An analyst who can click a byte and watch the RF that produced it illuminate has been handed something
no commercial decoder offers, and it is the visible form of the closure thesis: **the chain is modelled
end to end, so provenance is available end to end.** One afternoon of UI work, and it will be the thing
judges describe to each other afterwards.

### 4.8 · Read the theme tag — requirements (iii), (iv) and (v) describe the **CCSDS telemetry stack**

The problem statement is filed as **Category: Software · Theme: Space Technology**. Nothing in the visible
text mentions satellites, and every team will treat the theme tag as an administrative accident. It is not.
Line the enumerated requirements up against **CCSDS 131.0-B, *TM Synchronization and Channel Coding*** — the
standard every space agency on earth uses for telemetry downlinks
([Blue Book](https://ecss.nl/wp-content/uploads/2020/04/CCSDS-131.0-B-3_forECSS(Draft-16Oct2019).pdf),
[Green Book rationale](https://ccsds.org/Pubs/130x1g3e1.pdf)):

| PS requirement | CCSDS 131.0-B |
|---|---|
| (iv) *"short-constrained convolution codes with Viterbi decoding"* | Convolutional, **K = 7, rate 1/2, G = [171, 133] octal**, punctured to 2/3…7/8. The canonical short-constraint code |
| (iv) *"RS block codes"* | **RS(255,223)** (E = 16) and **RS(255,239)** (E = 8) over GF(256), systematic |
| (iv) *"Concatenated codes"* | RS **outer** + convolutional **inner** — precisely the arrangement §4.4 describes |
| (iv) *"LDPC"* | The AR4JA family plus the rate-7/8 C2 code |
| (iii) *"Block"* interleaving | RS **interleaving depth I ∈ {1, 2, 3, 4, 5, 8}** — a block interleaver, with I = 1 meaning none |
| (iii) *"Pseudo Random"* | The CCSDS **pseudo-randomiser**, applied between RS encoding and the sync marker |
| (v) *"bit stream correlation for identification of header and payload"* | **Attached Sync Marker → CADU → Transfer Frame**: a fixed 32-bit pattern at a fixed period, then header, then payload |
| (ii) *"Demodulate … PSK"* | CCSDS 401.0-B: BPSK / QPSK / OQPSK |

The standard's processing order is **RS encode → pseudo-randomise → attach ASM → convolutional encode**.
Compare §2.2's generic chain; they are the same chain.

**Four consequences, and the third is worth a week of the schedule:**

1. **You now know why the theme says Space Technology — and you can say so.** *"We noticed your requirement
   list is the CCSDS telemetry stack"* is the most credible opening sentence available to this submission,
   because it demonstrates you read the PS the way its author wrote it. No competing team will make the
   connection; it requires knowing the standard rather than knowing DSP.
2. **§4.3's descrambling argument gets sharper.** Part I calls the scrambler *"the layer the PS forgot."* More
   precisely: the PS's own implied standard puts a pseudo-randomiser **between two of the stages it did
   enumerate**. A team that implements (iii) and (iv) without it fails on the sponsor's most likely test data
   and will not understand why.
3. **Track A of §4.4 gets a free, fully specified, unambiguous first target.** CCSDS Blue Books are public
   and downloadable. **One cartridge family (§16.1) covers requirements (iii), (iv) and (v) at once** — with
   published polynomials, published interleaving depths, a published randomiser, a published sync marker, and
   reference implementations to validate against. No guessing, no reverse engineering. **This is the highest
   value-per-hour item in the entire project.** Build the CCSDS cartridge in week 5, before anything bespoke.
4. **It supplies a demo the theme is asking for** — see §9's revised Act 5.

**State the limit honestly, because a judge will:** the PS body describes *terrestrial* collection in
HF/VHF/UHF, and CCSDS is a space link. Both are true and they do not conflict — the body describes where the
files come from; the requirement list and the theme describe the coding you are expected to handle. The
coding layers are identical either way, and the cartridge architecture makes carrying both free.

---

## 5 · One residual, three products

The §3.2 fix — test the residual for structure, not only size — quietly turns SHRUTI's central quantity
into three distinct deliverables. Worth stating explicitly, because the economy of it is the strongest
architectural argument in the document:

| Reading of the residual | Test | Product |
|---|---|---|
| **How big is it?** | Goodness-of-fit against χ² with a model-error floor | Calibrated confidence and the honest UNKNOWN verdict |
| **Is anything still structured in it?** | Whiteness test, plus a cyclostationarity re-scan | **Weaker emitters hiding under stronger ones** (L4b peeling) |
| **What *kind* of structure is left?** | Feature extraction on the residual: phase-noise spectrum, PA nonlinearity signature, LO drift, filter mismatch | **Specific Emitter Identification** — see below |

### 5.1 · Specific Emitter Identification, for free

RF fingerprinting is a mature field, and this is not a claim to have invented it. What is new is the
**feature space**. Conventional fingerprinting throws raw IQ at a CNN and hopes device identity survives
into the embedding, where it is entangled with waveform, channel and content. SHRUTI has already
removed the waveform, the channel and the payload by construction — so:

> **The model residual is, by definition, the part of the signal that the standard does not specify.
> That is precisely where device identity lives.**

Two captures with identical recovered parameters but different residual signatures are two different
physical radios. Matching signatures across captures, dates and bands are one radio. For NTRO, telling
apart two units of the same model is a capability that no amount of modulation classification provides.

And it doubles as a self-diagnostic for the twin, which is a nice property to have discovered rather
than designed: **if residuals cluster by device, the twin is good. If they cluster by waveform type, the
twin has a systematic modelling error and you have just localised it.**

---

## 6 · The two sentences in the PS that everyone else will skim

Both are throwaway lines in the official text. Both are free differentiation, because answering a line
the sponsor wrote themselves is the cheapest credibility available.

### 6.1 · *"Recorded from different sensors and different locations, the parameters may vary"*

The PS is pointing at **multi-sensor reconciliation**, and no other team will notice. Three levels, in
increasing ambition:

1. **Per-sensor calibration.** Each sensor has its own artefact signature (§3.4), its own habitual
   sample rates and dtypes, its own clock error. Learn a per-sensor profile from its archive and
   *subtract the sensor* before analysing the emitter. This is exactly v1's L1 idea generalised from one
   receiver to a fleet, and it is what makes measurements from different sites comparable at all.
2. **Same-emitter association across captures.** Two files, two sites, two sample rates. Match the
   recovered parameter vectors within their error bars — this is the first place v1's error bars earn
   their keep operationally — then *confirm* by cross-correlating the recovered bitstreams (§4.6, step 4).
   Parameter agreement is suggestive; bit agreement is proof.
3. **Diversity combining.** Once two captures are confirmed to be the same transmission, combine their
   soft bits. Two marginal captures that each fail to decode can jointly succeed — and the moment they
   do, you have a decoded payload that *neither sensor could produce alone*. That is a direct, literal
   answer to the PS's complaint that the data is insufficient. If timestamps are trustworthy, the same
   cross-ambiguity machinery yields TDOA/FDOA, but treat geolocation as a stretch goal and say so.

### 6.2 · *"The spectral relationship from training data containing both .IQ and .wav formats"*

This line reads oddly until you notice it is an invitation to cross-format modelling, and that the twin
answers it **by construction** rather than by hoping a network discovers it:

> The `.IQ` file and the `.wav` file are two *renderings* of one underlying emitter — full complex
> baseband, and the real audio-band output of an SSB receiver applied to the same signal. SHRUTI's twin
> can render **both views from one parameter set**, because the SSB receiver is just another block in the
> chain. So the "spectral relationship" the PS asks about is not learned from paired data; it is a
> derivable transform, and the twin *is* that transform.

The practical consequences are large and cheap: one model covers both formats instead of two pipelines;
a signature library measured in one format transfers to the other; training data for L3 is generated in
both formats from the same generator at no extra cost; and a `.wav` and an `.IQ` capture of the same
emitter can be fitted **jointly**, against one shared parameter vector.

Say the sentence *"we render both formats from one model, so we don't need paired training data"* and you
have answered a line in the official text that most teams will not have parsed.

---

## 7 · The novelty claim, re-verified — and it got sharper

v1 §3 did the honest thing and searched. v2 searched again, with the bit layer in scope. The result is
better than v1's, because the gap is now **structural rather than incidental**: it is not that nobody got
around to this, it is that two mature literatures sit adjacent to each other and never touch.

### 7.1 · The two literatures

| | **Code-aided synchronisation** | **Blind code reconstruction** |
|---|---|---|
| Represented by | [Herzet et al., *Carrier and Clock Recovery in (Turbo-)Coded Systems: CRB and Synchronizer Performance*, EURASIP JASP 2005](https://link.springer.com/article/10.1155/ASP.2005.972); [Wymeersch & Moeneclaey, ML frame sync for turbo/LDPC](https://citeseerx.ist.psu.edu/document?doi=d9a7b40417826dba6e1ed1d9a6453dc9a8ea2cca&repid=rep1&type=pdf); [code-aided timing recovery in turbo receivers](https://arxiv.org/html/1509.03810v1) | [Sicot & Houcke, *Blind detection of interleaver parameters*, ICASSP 2005](https://unpaywall.org/10.1109%2FICASSP.2005.1415838); [Marazin et al., blind recovery of k/n convolutional encoders](https://jwcn-eurasipjournals.springeropen.com/counter/pdf/10.1186/1687-1499-2011-168); [interleaved convolutional codes](https://arxiv.org/html/1501.03715v1); [KS-test interleaver estimation](https://www.mdpi.com/1424-8220/21/10/3458/htm); [blind LDPC parameter recognition](https://www.researchgate.net/publication/327422048_Blind_Recognition_of_LDPC_Code_Parameters_over_Erroneous_Channel_Conditions) |
| Uses the decoder to | **Refine physical-layer estimates** — timing, phase, frequency | — |
| Recovers the code | No — **the code is known** | **Yes — this is the entire point** |
| Operates on | Your own designed link, synchronised receiver | **Bits**, assuming demodulation and synchronisation already succeeded |
| Physical layer | Fully known except small residual offsets | **Out of scope. Assumed solved by someone else** |

Read the last two rows together. **Each field assumes the other field's problem is already solved.**
Code-aided synchronisation needs the code; blind code reconstruction needs the bits. The actual NTRO
problem hands you neither — and the two halves need each other.

### 7.2 · The nearest misses, named before a judge finds them

| Work | How close it gets | Where it stops |
|---|---|---|
| [Blind Channel Estimation and Data Detection with Unknown Modulation and Coding Scheme (arXiv 1909.11306)](https://arxiv.org/html/1909.11306v1) | **The closest single paper.** Jointly estimates channel and noise power, recognises modulation *and* coding scheme, detects data, single or multiple receivers | Operates on synchronised matched-filtered baseband. Symbol rate, sample rate, pulse shape, CFO and interleaving are never in scope. Selects from a candidate MCS set rather than reconstructing an unknown code. No resynthesis, no residual verification, no open-set verdict |
| [Dualformer (arXiv 2606.31352)](https://arxiv.org/html/2606.31352) — verified real; v1's citation holds | Current SOTA feature extractor for blind signal analysis; defines AMR / SSR / **signal structure parsing** | Purely discriminative patch-token feature extraction. Writes the generative model down and never inverts it. No bits, no code, no residual |
| [Signal-Processing-Based DL for Blind Symbol Decoding (arXiv 2106.10543)](https://arxiv.org/html/2106.10543v2) | Interleaves DSP and NN estimators over rounds; gets to symbols | Feedforward refinement. No generative forward model, no FEC, no interleaver, no residual, no error bars |
| [Blind Turbo Demodulation for Differentially Encoded OFDM (arXiv 2511.21345)](https://arxiv.org/html/2511.21345v1) | Blind turbo iteration estimating phase, gain and noise variance jointly with decoding | Known code, known OFDM structure, designed link. "Blind" here means pilot-free, not parameter-free |
| [InverTwin (arXiv 2508.14204)](https://arxiv.org/html/2508.14204v1); [differentiable inverse rendering for RF twins (2603.18026)](https://arxiv.org/html/2603.18026); [NEMF (2603.02582)](https://arxiv.org/abs/2603.02582); [VLM-guided DRT (2601.18242)](https://arxiv.org/html/2601.18242v1) | Gradient inversion of differentiable RF models — and this cluster is **growing fast**, which strengthens the framing rather than threatening it | Every one of them inverts **propagation, geometry and materials.** Not one contains a symbol rate, a modulation, a code or an interleaver. Different inverse problem, adjacent method |
| [Nature Index: *Blind Recognition Techniques in Digital Communication Systems*](https://www.nature.com/nature-index/topics/l4/blind-recognition-techniques-in-digital-communication-systems) | Confirms this is a named, active research area — including Indian groups: [blind turbo/convolutional code parameter estimation](https://unpaywall.org/10.1016%2FJ.DSP.2019.102577), [*Characterization of Blind Code Rate Recovery in Linear Block Codes* (arXiv 2603.02031, Mar 2026)](https://arxiv.org/abs/2603.02031) — **verify author affiliations before naming institutions on a slide (§7.5)** | All of it downstream of demodulation, on hard or soft bits, with the physical layer assumed resolved. **Cite these — they are credibility, and a well-read judge may know them** |
| Analysis-by-synthesis as a paradigm | Won the speech-coding argument in the 1980s (CELP is literally analysis-by-synthesis) and is standard in vision | Never applied to blind RF exploitation. Searching for it returns compressed sensing, spatial audio coding and computer vision |

### 7.3 · The claim, in one paragraph

> Blind RF analysis is discriminative: it labels. Differentiable RF inversion exists, and is pointed at
> propagation and geometry. Code-aided synchronisation uses a decoder to sharpen physical-layer estimates,
> but only for a code it already knows, on a link you built. Blind code reconstruction recovers unknown
> codes and interleavers, but only from bits somebody else already demodulated. **SHRUTI joins the last
> two into a single differentiable objective in which the code hypothesis and the physical-layer
> parameters are estimated jointly — each one making the other possible — and then re-encodes the
> recovered bits, re-synthesises the waveform, and measures the difference against the original samples.**
> That specific combination returns nothing, and the reason it returns nothing is that the two fields it
> unites each assume the other's problem is already solved.

### 7.4 · Why it stays unclonable during the finale

v1's §7 argument holds and gains a fourth leg. The intersection now requires: the inverse-problem
reframe; DSP and autodiff in the same heads; the willingness to demo failures; **and coding theory over
GF(2) in the same team as the tensor work.** That fourth requirement is what makes it safe. A team that
sees your presentation cannot assemble it overnight — and the ones who could are working on a different
problem statement.

### 7.5 · Citation audit — completed 18 September 2026

Loophole 15 warned that some citations postdate ordinary verification. Every arXiv identifier in this
document was resolved against the arXiv API, and every non-arXiv link was checked for reachability. **Twelve
of fourteen arXiv citations verified exactly. Two did not, and both were in §4.5 — the table that answers the
strongest technical objection a judge can raise, which is the worst possible place for a bad reference.**

| Was cited as | Actually is | Action |
|---|---|---|
| arXiv 2401.14184, *"neural BCJR is standard"* | **"Friendly Attacks to Improve Channel Coding Reliability"** — not a BCJR paper at all | **Replaced** with [BCJRNet / Data-Driven Factor Graphs (2002.00758)](https://arxiv.org/abs/2002.00758) and [Communication Algorithms via Deep Learning (1805.09317)](https://arxiv.org/abs/1805.09317) |
| arXiv 2310.17758, *"fully differentiable BP decoders"* | **"Graph Neural Networks for Enhanced Decoding of *Quantum* LDPC Codes"** — adjacent, but quantum, not classical BP | **Replaced** with [Nachmani et al. (1607.04793)](https://arxiv.org/abs/1607.04793), the foundational weighted-BP-as-a-network result, plus [1706.07043](https://arxiv.org/abs/1706.07043) |
| `xplorestaging.ieee.org/...` scrambler paper | A *staging* host that returns HTTP 418 and will not survive | **Replaced** with the canonical [IEEE Xplore document 9802104](https://ieeexplore.ieee.org/document/9802104/) |

Confirmed exact, with publication dates: Dualformer (2606.31352, Jun 2026) · Differentiable Inverse Rendering
for RF Digital Twin (2603.18026) · NEMF (2603.02582) · VLM-Guided Differentiable Ray Tracing (2601.18242) ·
Blind Turbo Demodulation for Differentially Encoded OFDM (2511.21345) · Characterization of Blind Code Rate
Recovery in Linear Block Codes (2603.02031) · InverTwin (2508.14204) · Blind Channel Estimation with Unknown
MCS (1909.11306) · Signal-Processing-Based DL for Blind Symbol Decoding (2106.10543) · LDPC decoder training
recipes (2205.00481) · Blind identification of an unknown interleaved convolutional code (1501.03715) ·
WBSig53 / Large Scale RF Wideband Signal Detection (2211.10335). All non-arXiv links resolve.

**One claim remains unverified and should be softened or checked:** §7.2 attributes 2603.02031 to *IIT
Madras*. The paper is real and correctly titled; the affiliation was not confirmed. **Drop the institutional
attribution unless you check the author list** — an incorrect affiliation in front of an Indian judge who
knows the group is a needless, self-inflicted wound.

> **Do this audit again the week before the finale, and say on stage that you did it.** *"Every reference in
> our deck resolves; we checked, and we found two of our own that didn't"* is a small sentence that tells a
> technical panel exactly how you work.

---

## 8 · Correction — v1 names the wrong incumbents

v1 §10.1 builds its indigenisation argument on Rohde & Schwarz, Keysight and CRFS. Those are **spectrum
monitoring and measurement** companies. They are not the incumbents for this problem statement, and an
NTRO judge will know that immediately, which turns v1's strongest impact argument into a visible gap in
domain knowledge.

The actual incumbents for *blind demodulation, de-interleaving, FEC decoding and bitstream exploitation
across HF/VHF/UHF* are:

| Product | Vendor | Relevance |
|---|---|---|
| **Krypto500 / Krypto1000** | Comint Consulting (US) | The reference SIGINT/COMINT decoder suite: several hundred HF/VHF/UHF modem decoders plus blind analysis. [Vendor description](https://techbullion.com/market-leading-signals-intelligence-sigint-decoder-software-comint-consulting/) |
| **W-CODE / W61** | Wavecom (Switzerland) | *"All functions required to analyze, decode and process radio data communications throughout the spectrum (HF, VHF, UHF, SHF)"* |
| **CODE300-32** | HOKA Electronic (Netherlands) | Professional decoding and analysis suite for radio monitoring and technical investigation |
| **Decodio, R&S CA-series** | — | Adjacent monitoring-plus-decode systems |

And note what the enthusiast community says about all three: they include a **Signal Identification
mode** ([RadioReference decoder comparison](https://wiki.radioreference.com/index.php/Decoders)). So the
incumbents already do blind signal ID. **v1's §10.1 argument must be rebuilt on that fact rather than
around it**, and it is stronger afterwards:

> NTRO wrote SIH26147 in 2026 while Krypto500, W-CODE and CODE300-32 all existed and all do parts of this
> well. So the requirement was never capability in the abstract. It is **capability an Indian agency can
> lawfully own, read the source of, extend to an emitter that appears next month, and run air-gapped** —
> where the alternatives are foreign, closed, export-controlled, licensed per seat, and updated on
> somebody else's schedule. A closed decoder that does not recognise a new regional waveform cannot be
> made to. Ours can, by whoever holds the source.

**Do not stop at "expensive" — the vendor's own published terms give you a much sharper argument.** Krypto500
is ITAR-controlled with no trial or evaluation version of any kind, its *manuals* cannot be redistributed
without a licence, it is sold through NATO NSPA and US FMS/FMF channels, and the vendor states it is already
free to many agencies *through NATO, US and liaison channels* — channels India is not inside. **The
constraint was never price; it is access, on somebody else's terms, to something you may not read.** §20.1
develops this into the strongest form of the indigenisation case, with sources.

**The open-source landscape must also be named**, because it is what competing teams will fork:

| Tool | Does | Does not |
|---|---|---|
| [Universal Radio Hacker](https://www.usenix.org/system/files/conference/woot18/woot18-paper-pohl.pdf) | Demodulation plus automatic protocol-field labelling — **direct prior art for requirement (v)** and genuinely good at it | Short uncoded ISM/IoT packets. No FEC, no interleaver, no HF modems, hard decisions, no PHY parameter estimation |
| [SigDigger](https://github.com/batchdrake/sigdigger) | Blind analysis and demodulation of unknown signals, good UX | No FEC/interleaver reconstruction, no confidence, no resynthesis |
| [gr-inspector](https://github.com/gnuradio/gr-inspector) — GPL-3.0 | Wideband detection, channelisation, coarse classification | Stops at the channeliser. **Note:** the fork this document originally cited carries *no licence file at all* — cite upstream |
| [IQEngine](https://github.com/IQEngine/IQEngine) — **MIT** | Browser-based SigMF analysis, sharing and plugins. Permissively licensed, so it is legitimately reusable | No parameter estimation, no bits, no FEC. **Assume a competing team forks this for their GUI** |
| [TorchSig / WBSig53](https://arxiv.org/html/2211.10335v1) | Best open detection + recognition datasets and models | Assumes pre-channelised basebanded bursts, as v1 correctly noted. No bits |
| [`WB_Signal_Analyzer`](https://github.com/yuvaviva/WB_Signal_Analyzer) | The plumbing: memmap, dtype sniffing, BW/SNR, SigMF | v1's assessment stands. Carries no licence — do not copy it |

Assume a competent competing team arrives with **URH plus SigDigger plus a RadioML CNN**, which covers
requirements (i) and (ii) partially and (v) partially, in a weekend. That is the bar. Requirements (iii)
and (iv), the closure loop, and calibrated confidence are where the round is won.

---

## 9 · The demo — replace v1's four acts with this

v1's Act 2 reconstructs a waveform using a *statistically matched* random symbol sequence. It is a good
demo. v2 has a better one, and it is better in a way a non-specialist judge can verify with their own
eyes.

> **Every act below runs with no radio attached.** This is a **Software**-category problem statement, the PS's
> stated input is *"`.IQ` or `.wav` file as input data"*, and the Grand Finale is 36 hours at a nodal centre —
> a room with bad RF, no antenna, and no authority to transmit. **Build every act file-in, file-out.** Where
> hardware appears below it is an *optional rebuttal exhibit*, never a dependency, and every act has a
> file-based path that is the default. See §17.2.

### Act 1 · "Give me a file I've never seen." (75 s)

Unchanged from v1, plus the honest line about sampling frequency: SHRUTI announces the container format
it inferred and why, **states that absolute sample rate is not identifiable from samples alone**, then
solves it anyway from an in-band anchor and shows the evidence. Five emitters boxed, spurs crossed out,
measurement table with ± bounds. No dropdowns touched.

### Act 2 · Peeling. (45 s)

Fit the strongest emitter, subtract it, and watch a sixth emitter appear from underneath that was
invisible in the original spectrogram. *"That one was there the whole time. We could only see it because
we can build the one on top of it and take it away."*

### Act 3 · The blind Turing test — **this is the new centrepiece.** (150 s)

Hand a judge a keyboard and a button.

1. They **type any sentence.**
2. They press **Randomise.** The transmitter picks — in front of them — a random modulation, a random
   symbol rate from a wide set, a random RRC roll-off, a random interleaver type and depth, a random FEC
   from the four families in requirement (iv), and a random carrier offset. **The configuration is shown
   on screen and immediately covered.**
3. **The twin synthesises the capture in software** — carrier offset, timing error, AWGN, and a Watterson
   channel (§4.1) — and writes an unlabelled file to disk. **No radio, nothing to fail in the hall.** The
   generator is a *separate process* that shares no state with the analyser and hands over nothing but
   samples; show the two terminals side by side so this is visible rather than asserted.
4. SHRUTI receives an unlabelled file. It has been told nothing.
5. It prints: the sampling frequency, the modulation, the symbol rate with error bars, the interleaver
   type and depth, the FEC family and rate, the frame structure with the header segmented from the
   payload — **and then the judge's own sentence.**
6. Uncover the configuration. Compare, line by line, on screen.

Then close it:

> *"You chose the transmitter. We didn't get to see it. Every number on the left is a measurement, and
> the sentence at the bottom is the proof that the measurements were right — because if any one of them
> had been wrong, the error-correcting code would not have decoded, and you would be looking at noise."*

**No classifier-based team can attempt this act.** There is no partial-credit version of it: either the
sentence appears or it doesn't. And the randomise button is what makes it a proof rather than a
rehearsed trick — insist that a judge presses it, and press it twice.

**Have the rebuttal ready, because a sharp judge will say *"you generated the file yourself."*** They are
right to ask. Three answers, in ascending strength, and you should have all three loaded:

| Rebuttal | What it shows | Cost |
|---|---|---|
| **Separate processes** | Generator and analyser share no state, no seed, no config — only a file on disk. Show both terminals | Free |
| **Hold out the cartridge** | Press Randomise with a waveform whose cartridge is **removed from the analyser's library**, so track A cannot match and tracks B/C must reconstruct the code blind. *"It has never seen this one."* | A rehearsal |
| **Third-party capture** | Run the same pipeline on a **public dataset recording with published ground truth** that nobody on the team produced, and show the parameters agreeing | An afternoon |
| *(optional)* **Hardware loop** | Transmit into a **cable and attenuator** (§12) if the venue allows. Real oscillator, real front end, real impairments | Hardware, and it can fail |

**Lead with the hold-out-cartridge version.** It is a genuine blind test, it needs no radio, and it is the one
that actually answers the objection — the hardware loop proves the signal was real but proves nothing about
whether you knew the answer in advance.

### Act 4 · The honesty act. (90 s)

v1's Act 3, kept in full because it is still the act that wins the round, with two additions:

- A modulation held out of training → **UNKNOWN**, with a goodness-of-fit p-value shown above threshold,
  and every measurement still printed.
- A receiver spur → tagged **ARTEFACT — LO leakage**, with the reference-free test that caught it named.
- The reliability diagram: when SHRUTI says 80%, it is right about 80% of the time.
- **NEW —** a capture too short for FEC reconstruction → the capability **greys itself out** with the
  reason and the bit count required. *"It doesn't guess. It tells you what it can't know yet."*
- **NEW —** two captures of the same emitter from different sensors → same parameters, **same residual
  fingerprint**; then a second radio of the same model → same parameters, **different fingerprint.**

### Act 5 · The theme act — a CCSDS downlink, end to end. (60 s) — **REVISED**

v1's Act 4 was an FHSS emitter reported as one emitter with 47 hops. Keep it as a spare; it is a good visual
and it answers *"can it handle agile emitters."* But it is unrelated to this PS's theme, and §4.8 supplies
something that lands directly on it.

Run one file — a **CCSDS telemetry downlink**, synthesised or from a public recording — all the way through,
narrating each stage as it lights up:

> sync marker found at period 8920 bits → pseudo-randomiser stripped → Viterbi over K=7 r=1/2 →
> RS(255,223) de-interleaved at depth 5, **11 symbol errors corrected** → transfer frame header segmented
> from payload

Then the line:

> *"That's requirements three, four and five of your problem statement, in one file, against a published
> international standard. We built it first because we noticed your theme tag says Space Technology — and
> your FEC list is the CCSDS telemetry stack, in order."*

Close on the capability envelope, then SHRUTI-Bharat.

**Rehearsal rule.** Every act runs **file-in, file-out, offline, on the demo laptop** — that is the rehearsed
path, not the fallback. If you bring hardware for Act 3's optional rebuttal or a spare FHSS act, rehearse it
in the real room *and* record a fallback. **Nothing on the critical path may require a radio, a network, or
the venue's cooperation.**

---

## 10 · Evaluation — v1's table plus the bit layer

Keep every row of v1 §9. Hold out **entire modulation families and entire code families** from training,
never random splits. Add:

| Claim | Metric | Baseline to beat |
|---|---|---|
| Demodulation works | BER / SER vs SNR against a known-parameter reference receiver; gap to the perfect-knowledge bound in dB | GNU Radio receiver given the true parameters — **report the gap, do not hide it** |
| Interleaver identified | Correct (type, period, depth) rate vs SNR and vs bits available; false-identification rate | Published rank-deficiency methods on hard bits — the soft-syndrome track of §4.4 should beat them by several dB, and that delta is a publishable result |
| FEC identified | Correct (family, n, k, polynomials) rate vs SNR and vs bits; **p-value calibration** — do claimed 10⁻⁶ certificates hold up | Library-match-only track, and hard-decision reconstruction |
| Closure actually helps | Symbol-rate and CFO NMSE **before vs after** decode feedback, both plotted against the coded and uncoded CRLB | The physical-layer-only estimate. This single plot is the empirical proof of the §2 thesis — make it the hero figure |
| Payload recovered | End-to-end message error rate: judge's sentence in, sentence out | No baseline exists. That is the point |
| Header/payload segmentation | Field-boundary precision/recall on synthetic protocols with known framing | URH on the same streams |
| Fingerprint separates devices | Equal error rate, same-model different-unit pairs | Raw-IQ CNN fingerprinting on the same captures |
| Peeling finds buried emitters | Detection rate vs interference-to-signal ratio and spectral overlap fraction | Energy detector, and detection without peeling |
| Multi-sensor combining helps | Decode success rate: sensor A alone, B alone, A+B combined | Best single sensor |
| Sim-to-real gap is measured, not asserted | **Distribution of goodness-of-fit p-values on real captures vs synthetic** | v1's unsupported claim that real captures fit better. Measure it and publish whichever way it falls |

The second-to-last and last rows are the two that convert v1's weakest assertions into evidence.

---

## 11 · Risks and the revised descope ladder

New risks the bit layer introduces:

| Risk | Severity | Mitigation |
|---|---|---|
| L6 blind code reconstruction is the hardest single component and consumes a person | **High** | Library-match track (A) first — it works, it demos, and it covers most real traffic. Algebraic reconstruction (B) is the stretch. Never let B block A |
| Not enough bits in demo captures for L6 | **High** | Design the demo transmissions to be long enough on purpose, and gate honestly elsewhere (§3.6) |
| Closure loop does not converge; decode feedback destabilises the L4 fit | Medium | Only ever *refine* from a converged L4 point, with a trust region and a hard rollback if the goodness-of-fit worsens. The loop must be able to decline |
| GF(2) linear algebra over 10⁶-bit streams is slow | Medium | Bit-packed operations, restrict the hypothesis grid using the PS's own named families, profile early |
| Scope inflation — nine layers, six people, weeks | **High** | The ladder below. Rung 1 satisfies all five official requirements |

### The revised descope ladder — every rung still answers the PS

| Rung | What you keep | What survives |
|---|---|---|
| **Full** | Closure loop: decode feedback refines the physical layer, gradient inversion throughout | Everything, including the hero figure of §10 |
| **Rung 1** | Classical estimators → soft demod → **library-match** interleaver and FEC → bits → framing → resynthesis and residual as verification and confidence | **All five official requirements. Acts 1–5 all survive.** You lose only the closure figure and joint estimation. This is the target — build for this |
| **Rung 2** | As Rung 1, minus algebraic reconstruction of unknown codes; unknown codes return an honest *"interleaved and coded, structure not recovered"* with period and depth | Requirements i, ii, iii (partial), iv (partial), v. Still complete on the demo |
| **Rung 3** | v1 as written: L0–L4 + tracking + SigMF evidence sheet, no bits | **Now scores as incomplete against the official text.** Only acceptable as a fallback, never as the plan |

**Note the inversion from v1.** In v1 the reconstruction demo was the prize and gradients were insurance.
In v2 the *bits* are the prize and gradients are the ceiling: Rung 1 needs no autodiff at all, which means
the strongest demo in §9 does not depend on the riskiest component. **Build the forward twin and the
library-match FEC track first, in that order, and Act 3 is yours regardless of what happens to the
optimiser.**

---

## 12 · Team and sequencing — what changes

v1's six roles stand, with one reallocation and one addition. The **DSP lead** and **twin engineer** are
still the project. The change:

| Role | v1 | v2 |
|---|---|---|
| **Coding-theory lead** | — | **NEW, and non-negotiable.** Owns L5–L7: GF(2) linear algebra, blind code and interleaver reconstruction, Viterbi/BP/RS decoding, scrambler recovery, framing. Must read the Sicot–Houcke–Marazin line of work in week 1 |
| ML engineer | L3 proposal net, L5 curriculum, calibration | Same, **de-prioritised further.** The proposal network was seventh in v1's ordering; in v2 it is eighth |
| Product / evidence | Evidence sheet, plots, pitch | **+ the GUI**, which is now a named deliverable (§4.7). Budget real time for provenance brushing |

The honest disqualifier from v1 §14 now has a second clause: *if you cannot staff a DSP lead, a twin
engineer **and** somebody willing to do coding theory, pick a different problem statement.* That is three
of six on hard technical reading. It is the price of this PS, and it was always the price — the official
text just made it explicit.

### Build order (revised)

1. **Twin forward pass, synthesis only.** Validate against GNU Radio. Unlocks the reconstruction demos.
2. **L0 + L1 + L2** — container inference with the audio path, reference-free artefact tests, CFAR and
   tracking. Still the highest impact per hour in the project and still the least contested.
3. **L5 soft demodulation** — requirement (ii), and everything downstream needs soft bits.
4. **L6 track A, library match** — requirements (iii) and (iv) at Rung 1. Do this before track B.
5. **L7 framing and correlation** — requirement (v). Cheap once bits exist.
6. **Classical estimators with error bars, and the GoF statistic** — the honesty layer.
7. **SigMF output + evidence sheet + GUI**, end to end on one file, early. An ugly complete pipeline beats
   a beautiful partial one.
8. **L6 track B and C** — algebraic and soft-syndrome reconstruction. The research contribution.
9. **L4 gradient inversion and the closure loop.** Time-boxed. The ceiling.
10. **L5 capability envelope**, including the bits-required curves.
11. **Proposal network.** A speed optimisation, genuinely last.
12. **Live capture + rehearsal.** Twice, real hardware, fallbacks recorded.

The neural network is eleventh of twelve. Say that to the judges.

### One legal note v1 omits

v1 correctly warns that transmitting requires a cable and attenuator. Add the receive side: demonstrating
recovery of **third-party over-the-air traffic** is a different matter from transmitting, and in India
touches the Indian Telegraph Act 1885 and the IT Act. For an NTRO problem statement the authorisation
context is inherent, but for the demo and the repository, use **synthetic captures, your own
transmissions into a cable, and public datasets only** — and say so on stage. Volunteering that
distinction signals you understand the operating rules of the domain, which with this sponsor is worth
more than an accuracy point.

---

## 13 · Edit checklist against v1

If you keep v1 as the primary document, these are the specific changes. Nothing else in v1 needs to move.

| v1 location | Action |
|---|---|
| §1 pitch, §16 pitch spine | Rewrite around §2's thesis. The reconstruction line stays; add *"and then it reads the message"* |
| §2.4 reframe | Keep verbatim. It is the best paragraph in either document |
| §3 prior-art table | Add the two literatures of §7.1 and the near-misses of §7.2. Keep the InverTwin naming caution — the propagation-inversion cluster has grown since v1 |
| §3.5 *"our SigMF output is the input your 2023 FEC PS needed"* | **Delete.** It concedes the scope hole out loud. Replace with: *"your 2023 problem statement asked for the back half of this chain and your 2026 one asks for all of it — so we built all of it"* |
| §4 twin diagram | Extend the chain to include scrambler, interleaver, FEC encoder; add the closure feedback arrow |
| §5 L0 | Add the audio-baseband path, the identifiability statement, in-band anchoring (§3.3, §3.5) |
| §5 L1 | Replace the terminated-capture requirement with the reference-free tests (§3.4) |
| §5 L4 | Add the HF Watterson channel and the standards-lattice prior (§4.1); fix the error-bar method to the full Fisher information matrix; add the parameter-degeneracy discussion |
| §5 L4 *"do not try to recover the data bits"* | **Replace** with the three-regime objective of §3.1 |
| §5 L4 residual table | Replace the dB threshold with the goodness-of-fit statistic (§3.2) |
| **New sections after L4** | L4b peeling, L5 soft demod + descrambling, L6 interleaver/FEC, L7 bitstream — §4.2–§4.6 |
| §5 L6 SigMF schema | Add `shruti:fec`, `shruti:interleaver`, `shruti:frame`, `shruti:scrambler`, `shruti:gof_pvalue`, `shruti:fingerprint`, `shruti:payload_entropy_bits_per_bit`, `shruti:data_sufficiency` |
| §8 anti-pattern 4 | Soften. The GUI is a named deliverable; keep "engine first", drop "static HTML is enough" |
| §9 evaluation | Add the ten rows of §10 |
| §10.1 incumbents | **Correct** to Krypto500 / W-CODE / CODE300-32 and rebuild the argument as in §8 |
| §11 stack | Add: `galois` (MIT) for GF(2) linear algebra, **`commpy` (BSD-3)** for reference codecs, sigidwiki as the signature-library source, ITU-R F.1487 for the HF channel. **Do not use `komm` — it is GPL-3.0.** Full dependency audit in §18 |
| §12 demo | Replace with §9's five acts. Act 3 is the submission's centre of gravity |
| §13 descope ladder | Replace with §11's — Rung 1 must satisfy all five official requirements |
| §14 team | Add the coding-theory lead |
| §15 sequencing | Replace with §12's build order |
| §17 *"get the official PS text"* | **Done.** Replace that reminder with a line confirming the design is written against the official text, and keep the deadline/slot-cap warnings — verify those on sih.gov.in independently |

---

## 14 · The pitch spine — three sentences, rewritten

> **"Every tool in this space, commercial or academic, runs one way: samples to parameters to symbols to
> bits, each stage trusting the last, and it tells you a number it calls confidence. We run the loop
> closed — because a signal's error-correcting code is not the last obstacle before its payload, it is the
> most precise measuring instrument in the whole recording, and everybody throws it away.**
>
> **We were never given the transmitter's training sequence, so we built one out of its error-correcting
> code. Then we re-encode what we recovered, rebuild the waveform, and show you the difference against
> your original file. When that difference is noise, the analysis isn't confident — it's demonstrated,
> and you can read the message to check.**
>
> **It runs on a ₹2,000-class USB dongle — or on no radio at all — instead of a foreign export-controlled
> decoder suite that India cannot read the manual of. It is ours to extend when a new waveform appears next
> month, and extending it means writing a text file, not waiting for a vendor. It installs from a USB stick
> onto a machine that has never been online. And we will also show you the map of exactly where it breaks —
> because that is the difference between a demo and something NTRO could put in front of an analyst."**

---

# PART II — Why it ships

*Added 18 September 2026. Part I is the argument that SHRUTI is **right**. Part II is the argument that six
students can **build** it, that an agency can **run** it, and that it still exists in three years. Those are
three different arguments, and Part I only makes the first one.*

> **The honest diagnosis of Part I:** it is ~90% technical depth and ~10% "can this be shipped." Against the
> published SIH criteria that is a scoring error of the same shape as v1's GUI mistake — technically correct,
> strategically expensive. Part I would win a graduate seminar. Part II is what wins a government hackathon.

---

## 15 · What a government sponsor is actually buying

Start here, because it reorders everything that follows.

Every team in the room will pitch **accuracy**. Accuracy is table stakes, and it is also the single thing a
sponsor can least easily verify inside a fifteen-minute slot. What an agency is actually buying, in rough
order of how much it matters to the person who signs:

| What they buy | Why it outranks accuracy | Where SHRUTI answers it |
|---|---|---|
| **Strategic control** | A capability you cannot read, modify or rebuild is a capability you *rent*. The sponsor is NTRO; the alternative products are foreign and export-controlled (§20.1) | §18 licence audit — and it must be *audited*, not asserted |
| **A maintenance path that outlives the team** | Every SIH winner graduates in eighteen months. The sponsor's real question is *"who fixes this in 2029?"* and almost nobody answers it | §16.1 waveform cartridges, §21 sustainment |
| **Somewhere it is allowed to run** | An analysis tool that needs a cloud account is not deployable at NTRO at any price. This is a hard constraint, not a preference | §19 — air-gapped by default, network-denied by test |
| **Auditability** | A finding that cannot be independently re-derived is an opinion. Inter-agency work needs findings | §16.4 attestation bundles |
| **Honesty under uncertainty** | A tool that is confidently wrong once is never trusted again. Part I already understands this better than the field does | §3.2, §4.7, §10 — keep, it is the differentiator |
| Accuracy | Necessary. Not sufficient. Not differentiating | §10 |

**Say the first five out loud in the pitch.** Not one competing team will, and each of them is cheaper to
build than an accuracy point.

### 15.1 · The SIH rubric, and where Part I currently loses marks

The recurring idea-submission criteria across recent editions are *novelty of the idea, complexity, clarity
and detail in the prescribed format, feasibility, practicability, sustainability, scale of impact, user
experience,* and *potential for future work progression* — with the Grand Finale scored across innovation,
technical feasibility, impact and benefits, and architecture. **Verify the current year's exact wording on
[sih.gov.in](https://sih.gov.in/) yourself; treat the list below as the stable shape, not the letter.**

| Criterion | Part I as written | Gap | Fixed in |
|---|---|---|---|
| Novelty | **Outstanding.** §7 is stronger than most published related-work sections | None. Raise the ceiling anyway | §16 |
| Complexity | **Outstanding**, arguably *too* outstanding — nine layers reads as unbuildable | Needs a visible floor, not a taller ceiling | §17 |
| Feasibility / practicability | **Weak.** §11's ladder is good; there is no build cost, no hardware cost, no compute budget, no schedule | This is the largest single scoring hole in the document | §17 |
| Sustainability | **Absent.** Nothing says who maintains this after the finale | Second largest hole. Government buyers care disproportionately | §21 |
| Scale of impact | **Narrow.** The document addresses exactly one user at one agency | Dual-use is free here and nobody claims it | §22 |
| User experience | **Improving.** §4.7 fixed v1's error and provenance brushing is a genuinely great idea | Still no analyst persona, no install story, no time-to-first-answer | §23 |
| Clarity for a non-specialist | **Poor, and this is dangerous.** Roughly half the evaluators in the room will not be RF people | A χ² goodness-of-fit argument does not survive contact with a generalist judge | §24 |
| Business / commercial case | **Absent.** No buyer, no adoption path, no unit economics, no IP position | Government evaluators score this even on a non-commercial PS | §25 |
| Differentiation, stated plainly | **Implicit.** The evidence is everywhere; the summation is nowhere | A judge should be able to repeat *why you* after you leave the room | §26 |
| Future work progression | Implicit | Make it explicit — corpus, cartridges, research line | §21.3 |
| **Category and theme fit** | **Missed, both.** Part I never notes that this is a **Software** PS whose input is a file, and never notes the **Space Technology** theme at all | Two free, high-credibility wins that also *reduce* what you have to build | §17.2, §4.8 |

### 15.2 · The two-audience problem

The room contains an NTRO domain expert who will test §7 and §4.4, **and** generalist evaluators who will
score impact, feasibility and presentation. Part I is written entirely for the first one. A submission that
delights the expert and loses the generalists still loses.

The fix is not to dumb anything down. It is to give **every technical claim a one-line plain consequence**
directly beside it — the discipline §24 formalises. *"Goodness-of-fit p = 0.31"* is for the expert;
*"the leftover noise looks like noise, so nothing was missed"* is for everyone else, and it costs eleven
words.

---

## 16 · Four additions that raise the novelty ceiling

Part I's novelty claim (§7) is about the *method*. These four are about the *product*, which is the axis a
government buyer scores — and each one drops out of the existing thesis rather than bolting onto it.

> **Each one was searched for prior art before being claimed, and the claims below are what survived.** §16.1
> survived narrowed (the declarative idea exists; the *generative, blind* use of it does not). §16.2 survived
> narrowed (the theory is mature; shipping it per-field does not exist). **§16.3 did not survive as a novelty
> claim at all** and has been rewritten as an application of established work in a new setting. Do the same
> discipline on stage — §7.2's "nearest misses, named before a judge finds them" is the best habit in Part I
> and it must extend to Part II.

### 16.1 · Waveform cartridges — the waveform is **data**, not code

The twin is already a parameterised generative chain. Make that chain **declarative**: a waveform is a
~40-line YAML file describing blocks and parameter ranges, not a Python module.

```yaml
# cartridges/milstd188_110a_serial.yaml
id: mil-std-188-110a/serial-2400
band: HF
chain:
  - source:      {bits: payload}
  - fec:         {type: convolutional, rate: 1/2, K: 7, poly: [0o133, 0o171]}
  - interleaver: {type: block, rows: 40, cols: 72}
  - scrambler:   {type: additive, poly: 0o1001, seed: 0xBAD}
  - mapper:      {type: psk, order: 8, mapping: gray}
  - shaping:     {type: rrc, rolloff: 0.35}
  - modulator:   {symbol_rate_bd: 2400, centre_hz: 1800, ssb: usb}
priors:
  symbol_rate_bd: {values: [2400], tolerance_ppm: 50}
  centre_hz:      {range: [1500, 2000]}
identifiability: {centre_hz: absolute_if_sidecar_else_audio_relative}
```

One file, and **every layer picks it up at once** with no code written:

| Layer | What it gets from the cartridge, for free |
|---|---|
| Twin (L4) | A forward model it can synthesise and differentiate |
| Proposals (L3) | Labelled training data, generated on demand, in both `.IQ` and `.wav` (§6.2) |
| Standards lattice (§4.1) | A point in the lattice, with tolerances |
| Library match (§4.4 track A) | A parity-check matrix and interleaver spec to test against |
| Signature report | *"consistent with MIL-STD-188-110A serial"* instead of *"8-PSK"* |
| Capability envelope | Bits required, SNR floor, measured not guessed |

**Prior art, named before a judge finds it.** Declarative binary-format description is well-established —
[Kaitai Struct](https://kaitai.io/) compiles YAML-ish `.ksy` structure descriptions into parsers, and
Tektronix holds patents on a declarative protocol-description language whose runtime turns sampled physical
signals into protocol bitstreams on an oscilloscope
([US 10,628,284](https://image-ppubs.uspto.gov/dirsearch-public/print/downloadPdf/10628284),
[US 12,339,766](https://image-ppubs.uspto.gov/dirsearch-public/print/downloadPdf/12339766)). Waveform-viewer
plugin systems ([Surfer](https://link.springer.com/chapter/10.1007/978-3-031-98685-7_19),
[WAL](https://ics.jku.at/files/2022ASPDAC_WAL.pdf)) do the analogous thing for digital-design traces.

**What is new here is the direction.** Every one of those describes a **known** format so a **parser** can
read it. A cartridge describes a **candidate** waveform so a **generator** can synthesise it, and the
synthesis is then inverted against an unknown capture. Declarative-spec-drives-generative-model-drives-blind-analysis
returns nothing, and the three consequences are what a sponsor buys:

1. **Extending the tool stops being a software task.** An analyst who has read a modem's specification can
   add it. No Python, no rebuild, no release cycle. This is the mechanism that makes *"ours can be extended
   when a new waveform appears next month"* (§8) **true** instead of rhetorical — and if you cannot name the
   mechanism, an NTRO judge will assume you have not thought it through, because every vendor says that
   sentence.
2. **It draws the open/closed line exactly where a government needs it.** The engine is public and Apache-2.0;
   the cartridge library is data and can be tiered — public cartridges for civil standards, restricted ones
   for anything sensitive, classified ones held entirely inside the agency and never shipped. **NTRO can
   extend the tool with material it can never show you, without forking your code.** No open-source RF tool
   currently offers that boundary, and it is the difference between a project an agency evaluates and a
   project an agency adopts.
3. **Maintenance cost collapses.** The long-tail cost of a decoder suite is waveform coverage, not
   engineering. Moving coverage into data means the project survives the team graduating (§21).

**And it gives Act 3 a devastating sixth beat:** hand a judge a cartridge file, let them change
`rate: 1/2` to `rate: 3/4` and `rows: 40` to `rows: 64`, save, re-randomise, and SHRUTI decodes the waveform
that did not exist ninety seconds ago. *"We didn't add support for that. We didn't write any code. Somebody
described it."*

### 16.2 · The identifiability ledger — every output carries what **cannot** be known

§3.3 makes the identifiability argument for one quantity — absolute sampling frequency — and it is the
sharpest paragraph in Part I. Generalise it to every output.

**Borrow the theory; it is mature and you should not pretend otherwise.** Estimation theory already
classifies parameters as *globally identifiable* (one solution), *locally identifiable* (finitely many),
*set-* or *partially identifiable* (a subset or a combination is recoverable), and *non-identifiable*
(infinitely many) — and it already knows that **blind** estimation is identifiable only *up to an ambiguity*,
which is precisely why the Fisher information matrix comes out singular
([Identifiability](https://en.wikipedia.org/wiki/Identifiability),
[CRBs for blind multichannel estimation](https://arxiv.org/pdf/1710.01605)).

**What is new is not the theory. It is shipping it as a per-field output of a working tool.** A search for a
blind recognition system that emits a formal identifiability verdict as a first-class product returns
nothing; the field reports accuracy against ground truth it generated itself, so the question never arises.
Claim the product, cite the theory.

Every reported quantity is tagged with its identifiability class, machine-readable, in the SigMF output:

| Class | Meaning | Examples |
|---|---|---|
| `absolute` | Recovered on a physical scale | Occupied bandwidth once Fs is anchored; frame period in bits |
| `relative` | Known only as a ratio until an anchor is supplied | Everything in Hz from a headerless file (§3.3) |
| `up_to_rotation` | Known modulo a symmetry of the constellation | Absolute phase; QPSK quadrant; bit polarity before the code resolves it |
| `up_to_permutation` | Structure known, labelling not | Interleaver present with period *P*, permutation unrecovered (§4.4) |
| `up_to_affine` | Known up to scale and offset | Amplitude, absolute time-of-emission without a disciplined clock |
| `not_identifiable` | Provably unrecoverable from this evidence, with the reason | RF centre frequency from a mono SSB `.wav` with no sidecar (§3.5) |

**And the class is computed, not asserted — from a matrix Part I already builds.** Loophole 5 says to invert
the *full* Fisher information matrix rather than reading per-parameter curvature. Do that and the
identifiability ledger falls out of the same object for free:

```
Blind local identifiability holds iff the FIM has exactly as many singularities
as there are continuous blind ambiguities in the model.

  rank deficiency == expected ambiguity count  →  identifiable up to the known ambiguity  ✓
  rank deficiency >  expected                  →  an UNEXPECTED degeneracy — report it,
                                                  and report the identifiable *combination*
                                                  rather than the individual parameters
```

Three payoffs, and the middle one is the useful one operationally. The null space of the FIM **names the
degenerate direction**, so loophole 6's roll-off ↔ symbol-rate ↔ SNR degeneracy stops being a caveat in prose
and becomes a measured, reported quantity. When a parameter is only *practically* non-identifiable, the same
analysis says **what additional evidence would fix it** — a longer dwell, a second sensor, a sidecar — which
is exactly the `What would resolve it →` block in §23.2's UNKNOWN screen. And the constrained CRB you report
is only meaningful once you state the constraint set, which the ledger now does.

So add a `remediation` field beside every non-`absolute` class. **A tool that says "I cannot know this, and
here is what would let me" is strictly more useful than one that says "0.87".**

Four things follow, and the fourth is the one that matters:

- **It kills a whole class of silent error.** A downstream analyst who correlates two `relative` frequencies
  as though they were `absolute` gets a wrong answer with no warning. The ledger makes that a type error.
- **It makes §6.1 multi-sensor fusion correct rather than hopeful.** You may only combine measurements
  inside compatible identifiability classes. Right now Part I's §6.1 step 2 quietly assumes this.
- **It is the honesty thesis made machine-readable.** Part I's UNKNOWN verdict says *"I could not determine
  this."* The ledger says *"this is not determinable, here is the proof, and here is exactly what evidence
  would determine it"* — a strictly stronger and more useful statement.
- **It is a defensible research contribution in its own right.** The blind-recognition literature reports
  accuracy against ground truth it generated itself, so identifiability never surfaces as a question. A
  formal identifiability analysis of the blind RF exploitation chain, published with the tool, is a paper —
  and §15.1's *"potential for future work progression"* row wants exactly that.

### 16.3 · Cross-layer consistency — an **established** technique, applied one layer lower

**Correction first, because this one was overclaimed on the first pass and an NTRO judge would have caught
it.** Binding a physical-layer fingerprint to a claimed protocol identity and flagging the mismatch is a
mature, named research area — not a new idea:

| Prior art | What it does |
|---|---|
| [UCSC **CL-FP**, cross-layer device fingerprinting](https://ieeexplore.ieee.org/document/10279603/) | Explicit cross-layer framework; PHY features (EVM) bound to MAC-layer identity; >90% on MAC-spoofing detection |
| Transceiverprint ↔ MAC binding; CNN router-impersonator detection | The same idea in 802.11, going back years |
| [RFF-enhanced 5G AKA](https://www.sciencedirect.com/science/article/abs/pii/S0167404826000374) | Fingerprint bound to cellular identity to detect fake base stations |
| [US 11,581,962](https://image-ppubs.uspto.gov/dirsearch-public/print/downloadPdf/11581962) | **The attacker's countermeasure** — spoof the MAC, the protocol behaviour *and* synthesise matching RF characteristics, so the layers agree |

**So do not claim the idea. Claim the setting, which is genuinely different.** Every one of those works
operates on a **known** waveform, with a **known** framing, reading a **known** header field at a **known**
offset — 802.11's MAC address, 5G's identity exchange. They are cross-layer checks inside a standard you
already have the specification for.

> **SHRUTI performs the same check where the waveform, the framing, the field boundaries and the identity
> field are all *recovered blind* (§4.6) — and where the fingerprint comes from a residual against a model
> that was itself recovered blind (§5.1).** Nobody hands you the protocol. That is the contribution, and it
> is a narrow one, so state it narrowly.

The practical value for the sponsor is unchanged and still real — it is simply an *application* of both
layers rather than a new mechanism, and it is free because both layers already exist:

| Observation | Inference |
|---|---|
| Same header identity, **different** PHY fingerprint | Impersonation, spoofing, or a replaced radio |
| Different header identity, **same** PHY fingerprint | One radio running multiple identities — a cover network |
| Same PHY fingerprint *and* bit-identical payload at a later time | Replay, not a live transmission |
| Header claims a standard the recovered parameters violate (§4.1) | Deliberately modified or improvised equipment |

No layer-at-a-time tool can compute any of these on an unknown emitter — a classifier has no fingerprint, and
a decoder suite has no residual. Cost: one join, over data both layers already produce.

**Two limits, stated in the same breath, because the literature is clear about both:**

- **Fingerprint stability** across time, temperature, receiver and propagation is *the* open problem in RF
  fingerprinting — accuracy degrades when training and test conditions differ, which is why cross-receiver
  generalisation is an active research line ([arXiv 2510.09405](https://arxiv.org/pdf/2510.09405)). Report
  these as **flags for an analyst**, never as verdicts, with the equal-error rate from §10 beside each one.
- **A coordinated adversary defeats it.** US 11,581,962 describes synthesising RF characteristics to *match*
  the spoofed identity, so the layers agree. Cross-layer mismatch detection works because coherent
  multi-layer forgery is hard, **not because it is impossible.** Say so — volunteering the ceiling of your
  own capability is the single most credible thing you can do in front of this sponsor.

### 16.4 · The attestation bundle — an analysis another agency can check

The resynthesis thesis has an unclaimed corollary. If the analysis is *verified by rebuilding the waveform*,
then the verification is **portable**: ship the recipe and anyone can re-run it.

An **attestation bundle** is a single signed file containing the SigMF metadata, the full recovered parameter
vector, the identifiability ledger, the RNG seeds, hashes of every cartridge used, the exact engine version
and SBOM, and the residual statistics — plus one command:

```
shruti verify report.shruti-attest.zip
→ re-synthesises the waveform from the recorded parameters
→ recomputes the residual against the original capture
→ PASS: residual reproduces to 1e-12; goodness-of-fit p = 0.31; 4 cartridges verified
```

Why this is worth more to a government than to anyone else:

- **A finding becomes transferable.** Agency B does not have to trust Agency A's analyst, or Agency A's
  build. It re-runs the bundle.
- **It is a chain of custody for RF intelligence.** Immutable input hash, pinned engine version, recorded
  seeds, deterministic output. The provenance question that follows any technical finding into a briefing —
  *"how do we know?"* — has a command-line answer.
- **It makes regression testing free.** Every archived bundle is a test case. Re-run the corpus after any
  change and every historical conclusion is re-verified automatically. This is also, quietly, how the project
  stays correct after its authors leave (§21).
- **It is cheap.** Deterministic seeding, content hashing, a `verify` subcommand, and a signature. Days, not
  weeks — and it is the kind of engineering maturity that separates a prototype from something an agency can
  put in a process.

> **Pitch line:** *"Every other tool gives you an answer. This one gives you an answer and the receipt — and
> the receipt re-runs."*

---

## 17 · Feasibility, costed

The largest scoring hole in Part I. Fill it with numbers.

### 17.1 · What already exists versus what you actually write

Rung 1 of §11 — which satisfies **all five official requirements** — is roughly 70% assembly of permissively
licensed components. State this explicitly; "nine layers" sounds unbuildable until you show the inventory.

| Layer | Off the shelf | You write | Rough scale |
|---|---|---|---|
| L0 container/format | `numpy` memmap, `soundfile`, `sigmf` | dtype sniffing, `auxi`/`LIST` chunk parsing, filename conventions, audio-vs-IQ decision, in-band anchoring | ~800 LOC |
| L1 receiver self-model | `scipy` | four reference-free tests (§3.4) + cross-file consistency | ~400 LOC |
| L2 detection/tracking | `scipy.signal`, OS-CFAR is textbook | band segmentation, emitter tracker | ~600 LOC |
| L3 proposals | `torch`, `torchsig` (MIT) | small CNN, curriculum from the twin | ~500 LOC — **and it is 11th of 12 in the build order** |
| L4 twin | `torch` autodiff, `scipy` filters | the differentiable chain + cartridge interpreter | **~2,000 LOC — the project** |
| L4b peeling | — | subtract-and-rescan loop | ~200 LOC |
| L5 soft demod | `commpy` (BSD-3) reference implementations | timing/carrier recovery, soft-LLR output, ambiguity resolution, blind descrambling | ~1,200 LOC |
| L6 FEC/interleaver | `galois` (MIT) for GF(2); `commpy` Viterbi/RS | cartridge-driven library match (A); rank/dual-code search (B); **soft-syndrome test (C — the contribution)** | ~1,500 LOC |
| L7 bitstream | `numpy` | frame autocorrelation, entropy profiling, field typing, cross-capture correlation | ~600 LOC |
| L8 GUI | any web stack; [IQEngine](https://github.com/IQEngine/IQEngine) (MIT) is a usable reference for SigMF-in-browser | provenance brushing (§4.7) — the part worth the time | ~1,500 LOC |

**≈ 9,000–11,000 lines for Rung 1.** Large for a hackathon, entirely ordinary for six people over a term,
and the risk is concentrated in two boxes (L4 twin, L6 track C) that §11's ladder already isolates.

**The honest statement of the hard part:** L6 tracks B and C are research. L6 track A is a lookup against
cartridges and it is a week. *Never let B block A* — Part I's §11 already says this and it is the single most
important sentence in the risk section.

### 17.2 · Hardware — the honest answer is **none**

This is a **Software**-category problem statement. SIH's hardware edition is the one that funds and expects
physical prototypes; the software edition expects a working program. And the PS's own input contract is
unambiguous:

> *"take `.IQ` or `.wav` file as input data"*

**The deliverable is a program that reads a file.** Not a receiver, not an appliance, not an
integrated system. Say that plainly — a software-track team that arrives with a hardware story has, at best,
diluted its own pitch, and at worst told the panel it misread the category.

| Tier | Kit | Cost | Role |
|---|---|---|---|
| **T0 — file only · THE DELIVERABLE** | None. Public datasets + the twin's own synthesis | **₹0** | **All five official requirements. All five acts of §9. The entire scored submission** |
| T1 — receive *(optional)* | RTL-SDR class USB dongle | ₹1,500–2,500 generic RTL2832U + R820T2; ₹3,500–4,500 for a genuine RTL-SDR Blog unit in India | Collecting *your own* test captures during development. Useful, not demoed |
| T2 — transmit *(optional)* | HackRF One + 30–40 dB attenuator + SMA cable | ₹11,000 (clone) to ₹34,500 (genuine); cable/attenuator ~₹2,000 | Act 3's optional hardware rebuttal only, into a cable, never over the air (§12) |

**So the capital budget of the scored deliverable is ₹0.** Software licences: ₹0 (§18). Cloud: ₹0 (§19).
Hardware: ₹0 required, ₹2,000–₹40,000 optional and only for generating your own test data. Put *that* on the
slide — it is a stronger number than ₹40,000 and it is the accurate one.

Two corrections to carry into the pitch anyway, because the numbers still appear in §14 and §20:

- **The "₹2,000 USB receiver" line is defensible for a generic RTL2832U dongle but not for a genuine
  RTL-SDR Blog V4 in India — and the V4 is being discontinued.** Say *"a ₹2,000-class USB dongle"*, and note
  that the *tool* needs no dongle at all. An over-precise number that is wrong costs more than a range that
  is right, and a judge may own one.
- **Sub-₹15,000 HackRF units in India are clones.** If you buy one, say so. It strengthens the low-budget
  argument rather than weakening it.

**Where hardware legitimately appears in the pitch:** as the *source of the files*, in one sentence — *"these
recordings come from ₹2,000 dongles, not from a ₹40 lakh monitoring receiver, and the software doesn't care"*
— which is a **software portability** claim about tolerating cheap, impaired front ends (§3.4's artefact
tests), not a hardware claim. That framing scores. Bringing a radio does not.

### 17.3 · Compute — CPU-first, and say why

| Stage | Hardware | Why |
|---|---|---|
| L0–L2, L5, L7 | **CPU.** Any 8-core laptop | `numpy`/`scipy`, memory-bandwidth bound |
| **L6 all tracks** | **CPU, and it is genuinely fast** | GF(2) linear algebra is bit-packed XOR and `popcount`. A 10⁶-bit stream packs into 125 kB; rank computations run in registers. **This is the layer that sounds expensive and is not** |
| L3 proposals | CPU inference; GPU only for training | ~1 M parameters. Training is a free-Colab afternoon |
| L4 gradient inversion | GPU helps; **not required for Rung 1** | This is the ceiling, not the floor (§11) |

**The claim to make: Rung 1 runs end to end on an analyst's existing laptop, no GPU, no accelerator, no
cloud.** For the sponsor that is a deployment property, not a performance note — it means the tool goes where
the data already is instead of the data having to move (§19).

### 17.4 · Schedule, and the ordering that protects the demo

Map §12's build order onto weeks, and note which demo act each week unlocks:

| Weeks | Work | Unlocks |
|---|---|---|
| 1–2 | Twin forward pass + cartridge format. Validate against GNU Radio out-of-process (§18) | Synthesis. Training data. Act 3's transmitter |
| 2–4 | L0/L1/L2 + the audio path | **Act 1 complete** |
| 4–6 | L5 soft demod + descrambling | Requirement (ii); bits exist |
| 6–7 | L6 track A (cartridge library match) + L7 | **Requirements (iii), (iv), (v). Act 3 complete — this is the finish line** |
| 7–8 | GoF statistic, error bars, capability envelope, GUI end to end | **Act 4 complete** |
| 8–10 | L4b peeling; attestation bundle; identifiability ledger | **Act 2 complete.** §16.2, §16.4 |
| 10–12 | L6 tracks B/C; L4 gradient closure loop — **time-boxed, droppable** | The hero figure of §10 |
| Throughout | Rehearsal, fallback recordings, corpus | §9 |

**Act 3 — the centre of gravity — is complete at week 7 and depends on nothing after it.** Every remaining
week adds ceiling. That is the sentence that answers "is this feasible," and it is worth a slide of its own.

### 17.5 · The software deliverable — what a Software-category judge actually opens

Part I specifies *algorithms*. A software-track evaluator opens a **repository** and asks four questions in
about ninety seconds: what does it accept, how is it structured, how do I run it, and how do you know it
works. Answer all four on one slide.

**1 · The input contract.** The PS's first sentence is about file formats, so this table is the first thing
to get right — and completeness here is cheap, visible, and directly scored against requirement (i):

| Family | Accepted |
|---|---|
| `.wav` | PCM `int16` / `int24` / `float32`; **mono** (SSB audio baseband, §3.5), **stereo** (true stereo audio *or* I-in-left / Q-in-right IQ — decided by Hermitian and inter-channel tests); 8 / 11.025 / 16 / 22.05 / 44.1 / 48 / 96 kHz; RIFF `LIST/INFO` and the SDR `auxi` chunk parsed for centre frequency and timestamp |
| `.iq` `.raw` `.dat` `.bin` `.cfile` `.cs8` `.cs16` `.cf32` | Interleaved IQ in `int8` / `uint8` / `int16` / `int32` / `float32` / `float64`, little- and big-endian, with optional fixed header skip — **all inferred, none asked for** (§23.1) |
| SigMF | `.sigmf-meta` + `.sigmf-data`, and `.sigmf` tar archives. **Read and written** |
| Filename provenance | SDRSharp, gqrx, HDSDR, SDRuno, SDRangel, KiwiSDR conventions parsed for rate and centre frequency (§3.3) |
| Size | **Memory-mapped.** Files larger than RAM are normal, not an error |
| Outputs | SigMF metadata · attestation bundle (§16.4) · JSON/CSV report · PDF evidence sheet · decoded bitstream (binary + annotated hex) · plots as PNG/SVG |

**2 · Module structure.** Layers L0–L8 are not a diagram, they are **packages with enforced boundaries** —
each one importable, testable and replaceable on its own, talking through typed dataclasses rather than
through a shared blob. Two boundaries carry the product's weight and should be named as APIs on the slide:
the **cartridge interface** (§16.1 — a waveform is data crossing this line, never code) and the
**twin's forward/inverse pair** (everything else depends on it; nothing it depends on depends back).

**3 · How to run it.** One contract, two skins, GUI and CLI at parity (§23.1):

```
shruti analyse capture.wav --report out/ --attest        # the whole chain
shruti analyse *.iq --batch --resume                     # §19.2 T4 archive mode
shruti verify report.shruti-attest.zip                   # §16.4
shruti cartridge validate cartridges/*.yaml              # §16.1
shruti synth --cartridge ccsds/rs-conv --snr 6 out.sigmf # the twin, standalone
```

**4 · How you know it works — and this is the part that is genuinely unusual.**

> **The twin is a test oracle.** Almost no software project has ground truth; this one *generates* it. Every
> parameter SHRUTI is asked to recover is an input to the synthesiser, so a property-based test can draw a
> random configuration, render it, analyse it, and assert that every recovered value falls inside its own
> stated error bar — **millions of labelled test cases, for free, with no annotation effort whatsoever.**

| Level | What it does | Why it exists |
|---|---|---|
| Unit | Per-block numerics against closed-form or `commpy`/`scipy` references | Ordinary |
| **Property / round-trip** | `synth(θ) → analyse → θ̂`, assert \|θ̂ − θ\| within the reported bound, over randomised θ. Run thousands per CI job | **The differentiator.** It tests the *error bars*, not just the values — so §3.2's calibration claim is continuously enforced rather than measured once |
| Cross-validation | The twin's output against **GNU Radio**, out-of-process (§18.1) | The most credible correctness evidence available |
| Golden / regression | Every archived attestation bundle re-verified on every commit (§16.4) | Historical conclusions cannot silently rot |
| End-to-end | The five acts of §9, scripted, headless, offline | The demo cannot break unnoticed |

Plus the two non-functional gates that are also *claims* you are making on stage: the **network-denied CI job**
(§19.3) and an **offline cold-install test** on a clean machine (§23.3). Both fail the build, so both are true
on the day rather than hoped for.

**Say the oracle line out loud.** *"We can't run out of test data, because the thing we built to analyse
signals is the same thing that makes them."* It is the software-engineering form of the entire thesis, and it
is exactly the kind of answer a software-track judge is listening for.

---

## 18 · The licence audit — the section that could save the project

**This is not administrative.** The sponsor's entire reason for writing this problem statement is strategic
control (§8). A deliverable that is accidentally GPL-encumbered, or that vendors unlicensed code, hands the
sponsor a legal problem instead of a capability — and §13's current stack recommendation contains exactly
that trap.

Every SPDX identifier below was read from the project's own repository metadata, September 2026:

| Component | Licence | Verdict |
|---|---|---|
| `numpy`, `scipy`, `pandas` | BSD-3 | ✅ Use freely |
| `galois` | **MIT** | ✅ The GF(2) workhorse. Use it |
| `commpy` (scikit-commpy) | **BSD-3** | ✅ Reference Viterbi/RS/interleavers |
| `torchsig` | **MIT** | ✅ Datasets and baselines |
| `torch` | BSD-3 | ✅ |
| [`IQEngine`](https://github.com/IQEngine/IQEngine) | **MIT** | ✅ Browser SigMF toolkit — a legitimate GUI reference, and **the thing a competing team will fork** |
| `sigmf-python` | **LGPL-3.0** | ⚠️ Import as an unmodified library, do not vendor or patch. Attribute |
| SigMF **specification** | CC-BY-SA-4.0 | ⚠️ Spec, not code. Attribute; do not paste the text into your docs |
| VOLK | LGPL-3.0 | ⚠️ Same treatment |
| **`komm`** | **GPL-3.0** | 🚫 **§13 recommends this. Remove it.** Use `commpy` + `galois` instead |
| **GNU Radio** | **GPL-3.0** | 🚫 **Never link.** Invoke out-of-process as a validation oracle only (below) |
| **URH** | **GPL-3.0** | 🚫 Benchmark against it (§10). Never copy a line |
| SigDigger | LGPL-3.0 | ⚠️ Reference only |
| `gr-inspector` | GPL-3.0 upstream | 🚫 And note: **the URL §8 cites is a zero-star fork carrying no licence file at all.** Cite [`gnuradio/gr-inspector`](https://github.com/gnuradio/gr-inspector) |
| `WB_Signal_Analyzer` | **no licence** | 🚫 Part I is right. No licence means no rights. Do not copy |

### 18.1 · The three rules that follow

1. **Core stays Apache-2.0.** Permissive, patent-granting, and — the point — it lets NTRO fork privately,
   classify the fork, and never publish it. Copyleft on the core would not legally block internal government
   use, but it *will* create a procurement conversation nobody wants to have, and for this sponsor the ability
   to build a closed derivative is the entire value proposition (§15).
2. **GNU Radio is an oracle, not a dependency.** You want it — validating the twin against GNU Radio is the
   single most credible correctness claim available (§12 build step 1). Keep it in a **separate dev-only
   container, invoked by subprocess over files.** No imports, no linking, no shared address space. The
   validation evidence ships; the GPL does not.
3. **Cartridges and corpus are CC-BY-4.0, separately from the code.** Data and code licensed apart is what
   makes §16.1's tiering work.

### 18.2 · Why this is a *scoring* argument, not a footnote

The Government of India's [Policy on Adoption of Open Source Software](https://www.meity.gov.in/static/uploads/2024/05/policy_on_adoption_of_oss.pdf)
states that OSS shall be adopted in e-governance systems **as the preferred option over closed source**, and
names its objectives as *strategic control* and *reduced total cost of ownership* — the two arguments this
document has been making all along. The policy also notes that "Free" means freedom to use, not free of
charge, which is precisely §21's business model.

> **One slide: "Licence audit — every dependency, verified."** It takes twenty seconds, no other team will
> have done it, and to a government evaluator it reads as the difference between a project and a product.

---

## 19 · Deployment — five targets, ₹0 recurring, and one thing you must **not** say to NTRO

### 19.1 · The trap

There is a strong instinct in hackathons to pitch *"and it deploys free on cloud."* **For this sponsor that
sentence actively loses marks.** NTRO is a signals-intelligence organisation. Intercept data does not go to a
third-party cloud, free tier or paid, Indian region or not. A team that pitches cloud deployment to NTRO has
announced it does not understand the customer.

**Invert it. Zero cloud is a feature, and it is the strongest deployment claim in the document:**

> *"SHRUTI never needs a network. Not for licensing, not for models, not for updates, not for telemetry. It
> installs from a USB stick onto a machine that has never been online, and we ship a test that proves it."*

The free-tier story still matters — but for the **judging round and the civilian spin-offs** (§22), not for
the sponsor. Say which is which, out loud. That distinction is itself evidence of domain understanding.

### 19.2 · The deployment ladder

| Target | Cost | Who it is for | What it proves |
|---|---|---|---|
| **T0 · Static browser demo** — pre-computed analyses of a few captures, waterfall/constellation/provenance brushing, on GitHub Pages | **₹0** | Judges, before and after the slot | A judge opens it **on their phone during your talk**. Zero install, zero trust required |
| **T1 · Colab notebook** — full Rung-1 pipeline, upload a file, get a report | **₹0** | Evaluators, reviewers, students | *"Try it yourself right now."* Honest limits: ~12 h session cap, ~90 min idle timeout, ~12 GB RAM, T4 **not guaranteed** — so the notebook must run **CPU-only** end to end (§17.3 makes that true) |
| **T2 · Hugging Face Space** — hosted civilian demo | **₹0** | Public, academia, the civilian users of §22 | Continuous availability without infrastructure |
| **T3 · Offline installer → air-gapped analyst laptop** — `docker save` tarball or a self-contained bundle with a vendored wheelhouse, SBOM, and checksums | **₹0** | **The sponsor. This is the real product** | Installs with no network, on Windows or Linux, in under five minutes |
| **T4 · Batch mode over an archive** — headless CLI, one attestation bundle per capture, resumable | **₹0** | The agency's existing storage | §20.3 — the highest-value deployment and nobody will pitch it |

**T3 is the deliverable. T0–T2 are how the room gets to touch it.** Build T3 first; T0 and T1 fall out of it
in an afternoon.

### 19.3 · The no-egress pledge, made testable

Anyone can *claim* their tool is offline. Make it a build artifact:

```
CI job: run the full pipeline inside a network-denied namespace.
        Any socket() call fails the build.
Result: a green badge that means "this binary cannot phone home", checked on every commit.
```

Add a **CycloneDX SBOM** and pinned hashes for every dependency, generated in CI. Total effort: a day.
Credibility with a security-cleared evaluator: disproportionate. Almost no student project ships a *testable*
security property, and this one is three lines of CI config.

### 19.4 · Sensor-side triage — the deployment split that saves real money

Run L0–L2 on a Raspberry-Pi-class box at the sensor; forward only what survives detection, with its metadata.
Run L3–L8 at the analyst's desk. **Same codebase, two configuration profiles — no hardware is designed, built
or required.** This is a deployment option for an agency that already owns sensors, described because it is
where the money is; it is not a change of category (§17.2).

The arithmetic, at a single 8 Msps `int16` complex sensor:

| | Volume |
|---|---|
| Raw | **32 MB/s** = **2.76 TB per sensor-day** |
| Ten sensors, one year, raw | **≈ 10.1 PB** |
| Ten sensors, one year, after edge triage at 1% duty cycle | **≈ 0.10 PB (101 TB)** |

**Two orders of magnitude.** At an illustrative ₹3,000/TB for nearline storage — state the assumption, the
number is indicative — that is roughly **₹3.0 crore of storage per year reduced to ₹3.0 lakh**, before
counting the backhaul that never has to carry it.

This is the clearest rupee figure in the entire submission, it requires no new hardware, and it comes free
from having built L2 anyway. **Put it on the business slide.**

---

## 20 · The economics — and a correction to §8's argument

### 20.1 · The incumbent argument is about **access**, not price — and that is far stronger

§8 correctly replaces v1's wrong incumbents with Krypto500/W-CODE/CODE300-32. The *argument* built on them
still needs work, because "foreign software is expensive" is weak and a judge may know that agencies
sometimes get it cheaply. Here is what the vendor actually publishes:

- Krypto500/Krypto1000 are **ITAR-controlled**. There are **no demo, trial, evaluation, time-limited or
  "light" versions — no exceptions** — and **the user manuals cannot be distributed without a licence**
  ([COMINT Consulting FAQ](https://www.comintconsulting.com/faq)).
- Sales run through defence acquisition channels: the vendor is registered under **NATO NSPA**, NATO
  Partnership for Peace, and the US **FMS/FMF** programmes ([about](https://www.comintconsulting.com/about)).
- The vendor states the software is **"already available at no cost to many agencies through official
  acquisition vehicles"** — accessible through *established NATO, U.S., and liaison channels*
  ([vendor post](https://www.comintconsulting.com/post/comint-consulting-sigint-software-no-cost)).

Read that last bullet the way NTRO reads it:

> **The foreign option is free — to countries inside an alliance structure India is not part of.** The
> constraint was never the price. It is that the capability is granted, on somebody else's terms, in a
> version you cannot read, cannot extend, cannot audit, and cannot be certain still works the way it did
> last year. You cannot even lawfully hand the manual to the analyst next to you.
>
> **That is not a procurement problem. It is a sovereignty problem, and it is the actual reason SIH26147
> exists.**

Deliver that paragraph and §8's indigenisation case stops being a slogan. Then land it:

> *"We are not offering a cheaper Krypto500. We are offering the one thing it structurally cannot be:
> **yours.** Read the source, extend it with a text file, run it air-gapped, and when a new waveform shows up
> over Ladakh next month, nobody has to approve anything."*

### 20.2 · The cost table a government evaluator will actually read

| | Foreign decoder suite | SHRUTI |
|---|---|---|
| Licence | Quote-only, ITAR-controlled, alliance-channel | **₹0**, Apache-2.0 |
| Source access | None | **Complete** |
| Export/end-use restriction | Yes | **None** |
| Documentation | Cannot be redistributed without a licence | Public, in-repo |
| Add a new waveform | Vendor release cycle, if they agree | **One YAML file, any analyst, same day** (§16.1) |
| Air-gapped operation | Vendor-dependent | **Default, and CI-tested** (§19.3) |
| Per-seat cost to scale to 50 analysts | Per-seat negotiation | **₹0** |
| Audit a past conclusion | Not possible | **`shruti verify`** (§16.4) |
| Classified extension | Impossible | **Cartridge tiering; private fork** (§16.1, §18.1) |
| Build cost | — | **≈ ₹40,000 hardware + student time** (§17.2) |
| Recurring cost | Licence + support + upgrades | **₹0 software; storage reduced ~100×** (§19.4) |

### 20.3 · The three costs that are not the licence

The business case is not really the licence fee. It is these, and each maps to a capability already in the
design:

| Cost | Today | With SHRUTI | Mechanism |
|---|---|---|---|
| **Storage and backhaul** | ~10 PB/year across ten sensors | ~0.1 PB/year | §19.4 edge triage |
| **Analyst hours** | The PS's own opening line: *"The analysis is being carried out manually."* One unknown burst is hours of skilled work | Minutes, with the analyst spending their time on the UNKNOWNs instead of the routine | §9 Act 1, §23 |
| **Waveform lag** — the interval between a new emitter appearing and any tool being able to read it | Vendor release cycle: months, or never | **Same day**, by whoever holds the specification | §16.1 cartridges |

**And the unlocked asset, which is the largest number of all:** the agency's archive. Years of captures
recorded and never analysed, because manual analysis does not scale to them. §19.4's T4 batch mode runs the
whole archive overnight and produces an index — and §3.4's cross-file consistency and §4.6's cross-capture
correlation get *strictly better* the more files exist.

> *"The highest-value signal intelligence you own is the data you already collected and never had the hours
> to look at. This runs over all of it, on the hardware you have, this week."*

That sentence is the business case. It requires no new sensor, no new licence, and no new budget line.

---

## 21 · Sustainability — who maintains this in 2029

The question every government evaluator asks and almost no SIH team answers. *"You graduate in eighteen
months. Then what?"*

### 21.1 · The structural answer: move the long tail into data

A decoder suite's maintenance cost is **waveform coverage**, and coverage grows forever. §16.1 moves coverage
out of code and into cartridges, which means the thing that needs continuous maintenance no longer requires
the original engineers — or any engineers. **That is the whole sustainability argument, and it is
architectural rather than aspirational.** The engine is a bounded, finishable artifact; the library is
data that domain experts extend.

§16.4's attestation bundles are the second half: every archived analysis is a regression test, so the
project's historical correctness is checked automatically by people who never met the authors.

### 21.2 · The model: free software, paid expertise

Ranked by how realistic each is, not by how good it sounds:

| Path | What it is | Realism |
|---|---|---|
| **1 · Institutional adoption + a student pipeline** | The code lives in an institutional repo with a faculty owner and a rolling intake of final-year projects and interns. This is how most durable academic infrastructure actually survives | **High.** Costs nothing. Start it before the finale — it makes the sustainability slide true on the day |
| **2 · Services around free software** | The Red Hat model: the engine is free; integration, cartridge authoring for classified waveforms, training, support and per-sensor tuning are contracted. Explicitly compatible with [MeitY's OSS policy](https://www.meity.gov.in/static/uploads/2024/05/policy_on_adoption_of_oss.pdf), which defines "free" as freedom, not price | **High**, and it is the only model a government can procure cleanly — no lock-in, no export licence, GeM-listable |
| **3 · Dual-use civilian deployment** | §22. Same binary, different cartridges, wholly unclassified customers | **Medium.** Real, slower |
| **4 · Corpus and benchmark leadership** | §21.3 | **Medium**, and it is the moat |

### 21.3 · SHRUTI-Bharat — the corpus is the moat

**The gap is confirmed and it is wide.** There is no India-specific open, labelled RF corpus. The closest
labelled HF set is [Panoradio HF](https://panoradio-sdr.de/overview-of-open-datasets-for-rf-signal-classification/)
— 18 shortwave classes at 6 kHz, 2048-sample records. And the field's default benchmark has a documented
problem that is *directly relevant to this problem statement*:

> Sustained sample-level analysis of DeepSig's RadioML sets by Chad Spooner finds that **the symbol rate and
> carrier offset never significantly change, and the pulse-shaping roll-off does not appear to be varied at
> all**, alongside a "preoccupation with very short data records"
> ([CSP Blog](https://cyclostationary.blog/2020/09/24/deepsigs-2018-data-set-2018-01-osc-0001_1024x2m-h5-tar-gz/)).
> Independent work reaches similar conclusions on diversity and impairment realism
> ([Large Scale RF Signal Classification](https://arxiv.org/pdf/2207.09918)).

**Read what that means for this problem statement.** Requirement (i) asks for the sampling frequency and the
modulation. A team that trains on RadioML is training on data in which *the symbol rate and roll-off barely
vary* — the exact quantities SHRUTI is asked to recover. Their model has never seen the axis it is being
tested on.

So:

- **State it in §7 or §10.** *"The standard benchmark does not vary the parameters this problem statement
  asks us to measure."* It is verifiable, it is devastating to the classifier-first approach, and it explains
  in one line why analysis-by-synthesis is the right architecture here rather than merely a fashionable one.
- **The twin fixes it by construction.** Every parameter varies because every parameter is a parameter.
  Records are as long as you want. Labels are exact because they are the generator's inputs. And §6.2 renders
  `.IQ` and `.wav` from the same parameter vector, which no existing dataset does at all.
- **So the corpus is a by-product, not a cost.** Publish **SHRUTI-Bharat**: SigMF-native, CC-BY-4.0, HF/VHF/UHF
  focused, Watterson-faded per ITU-R F.1487 (§4.1), paired `.IQ`/`.wav` renderings, full parameter ground
  truth, the generating cartridges, **and the identifiability ledger for each record** — which no dataset
  anywhere currently provides.

Three things follow, and the third is the moat. It becomes the reference benchmark for blind RF exploitation
in India; it makes the work citable and reproducible, which is what §15.1's "future work progression" row
wants; and **a competing team can fork your code in a weekend but cannot fork the corpus, the cartridge
library, or the institutional relationship that keeps both growing.**

---

## 22 · Dual-use — the civilian products that fall out for free

§15.1's weakest row is *scale of impact*, because Part I addresses exactly one user at one agency. Fix it
without building anything: the same engine, different cartridges.

| User | What SHRUTI does for them | Marginal work | Reuses |
|---|---|---|---|
| **WPC / DoT spectrum enforcement** | Find, identify and characterise unlicensed or interfering emitters from a recording; automatic report with evidence and error bars | Cartridges for licensed Indian services | L0–L4, L8 |
| **Telecom operators** | Interference hunting: identify the interferer's waveform rather than only its power | None | L2, L4, L4b peeling |
| **ISRO / NewSpace ground stations** | Anomaly analysis on downlinks — did the modulation, rate or coding drift from spec? §4.1's non-conformance detection is exactly this | CCSDS cartridges (already public standards) | L4–L6 |
| **Railways, RRTS, metro PMR** | Verify the air interface of deployed radio equipment against its specification; acceptance testing without vendor tools | TETRA/LTE-R cartridges | L4–L7 |
| **Disaster and emergency response** | Triage a crowded HF/VHF band fast; find the weak station under the strong one (§4.2 peeling) | None | L2, L4b |
| **Drone / counter-UAS** | Identify controller and telemetry links by waveform and by **physical fingerprint** (§5.1), distinguishing two units of the same model | ISM cartridges | L4–L6, §5.1 |
| **Every ECE department in India** | A free, readable, runnable teaching tool for modulation, coding, interleaving and synchronisation — that *shows its work* | Notebooks | All of it |
| **Research community** | The corpus and benchmark of §21.3 | None | — |

Two arguments for the panel:

1. **Scale of impact, honestly earned.** One codebase, eight user communities, one budget. That is what the
   criterion is asking for, and it is true rather than aspirational because the cartridge architecture is what
   makes it true.
2. **The teaching row is not filler.** A tool that renders every intermediate stage — waterfall, constellation,
   soft bits, syndrome, frame map — with provenance brushing between them (§4.7) is a better pedagogical
   instrument than anything currently free. That is a real national contribution and it costs a README.

---

## 23 · Ease of use — the three-click rule and the "no DSP degree" mode

§4.7 fixed v1's GUI error, but it still describes the interface as views rather than as a *user*. The user is
an intelligence analyst, not a DSP engineer. Design for them.

### 23.1 · The rules

| Rule | Concretely |
|---|---|
| **Three clicks** | Drop file → one screen of answers → one button to export the attestation bundle. Everything else is optional depth |
| **Zero configuration to first answer** | No dialogue asking for sample rate, dtype, or centre frequency. **L0 infers all of it, says what it inferred and why, and lets you override.** Every competing tool opens with that dialogue — refusing to is a visible, demonstrable differentiator in the first ten seconds of Act 1 |
| **Anytime results** | Something on screen in **2 s** (detections, bandwidth, waterfall), refined at **30 s** (modulation, symbol rate, constellation), complete at **~5 min** (bits, FEC, framing). The analyst is never staring at a spinner — and §3.6's loophole 13 is answered by architecture rather than by a promise |
| **Plain language first, evidence behind it** | Headline: *"Digital, 8-PSK, 2400 Bd, consistent with MIL-STD-188-110A. High confidence."* Hover or click for the χ² p-value, the covariance matrix, and the identifiability class. **Both audiences of §15.2, same screen, no compromise** |
| **CLI/GUI parity** | Everything the GUI does, the CLI does, scriptable and batch-able. This is what makes §19.2's T4 archive mode exist at no extra cost, and analysts with a thousand files will use it |
| **Bilingual UI** | English/Hindi labels. A day of work with a string table. For a Government of India deliverable it is a visible signal of who this was built for |
| **Docs ship offline** | The help is in the bundle, not on a website. On an air-gapped machine there is no website (§19) |

### 23.2 · The UNKNOWN screen is the most important screen

When SHRUTI declines, it must be the most *useful* screen in the product, not an error:

```
VERDICT: UNKNOWN — the model does not explain this signal.
  Goodness-of-fit p = 0.002 (residual is not consistent with noise)
  Closest hypothesis: 16-QAM @ 4800 Bd, Δ log-likelihood 14.2
  Residual is structured at 1.2 kHz spacing — possible unmodelled multipath
  Capability gated: FEC reconstruction needs ≥ 20 kbit; this burst holds 3.1 kbit

  What would resolve it →  a longer capture of the same emitter
                           a sidecar with the tuned frequency
                           a cartridge for this waveform family   [ Author one ]
```

Every measurement it *could* make is still printed. The refusal names its own cure. And the last line routes
the analyst straight into §16.1 — **the tool's failure mode is an invitation to extend it**, which is what a
sustainable product looks like.

### 23.3 · Installation, which is where government tools go to die

| Path | Command |
|---|---|
| Try it, no install | Open the T0 page, or the Colab link |
| Analyst laptop, networked | `pip install shruti` — or one installer, Windows and Linux |
| **Analyst laptop, air-gapped** | Copy one folder from a USB stick. `./shruti`. **No network, no admin rights, no Python knowledge** |
| Archive / server | `docker load` from the same tarball |

**Rehearse the air-gapped install in front of the judges if there is time.** Pull the network cable, install
from a USB stick, analyse a file. Sixty seconds, and it makes the deployment claim physical instead of
verbal.

---

## 24 · The one-slide version, for the half of the room that is not RF people

§15.2's problem, solved. A generalist evaluator needs to be able to repeat your idea to another evaluator
after you leave. Give them the words.

> **The problem.** India's agencies record radio signals they cannot read. Right now an expert sits with each
> recording and works out, by hand, what kind of signal it is — which can take hours, and there are years of
> recordings nobody has ever opened.
>
> **What everybody else builds.** A classifier: software that looks at a recording and guesses a label, the
> way an app guesses a song. It is usually right, it cannot tell you when it is wrong, and it stops at the
> label.
>
> **What we build.** Instead of guessing what the signal *is*, we work out **how to rebuild it** — and then
> we rebuild it and compare. If our reconstruction matches the recording, we didn't guess right, we
> *demonstrated* it. And once we can rebuild the signal, we can finish the job: undo the scrambling, correct
> the errors, and read the actual message.
>
> **The line that makes it land.** *Every radio message carries its own error-correcting code — spare
> information the transmitter adds so the receiver can fix mistakes. Everyone treats that as the last
> obstacle before the message. We use it as a **measuring instrument**: if our settings are even slightly
> wrong, the error correction fails. If they are exactly right, it works and the message appears. So the
> message is the proof that the measurements were correct.*
>
> **Why the government should care.** It is free and open source, so India owns it and can extend it. It runs
> on an ordinary laptop with no internet connection, which is where this data is legally allowed to live. A
> new kind of signal can be added by writing a short text file — not by waiting for a foreign vendor. It
> costs about ₹40,000 to build. And it tells you when it doesn't know, which is the only reason anyone would
> ever trust it.

**If a judge remembers one thing, make it the error-correction line.** It is the whole thesis, it requires no
background, and it is unusual enough to repeat.

---

## 25 · The business case, end to end

§20 costed it. §21 said who maintains it. This section covers what neither does and what a business-minded
evaluator will ask: **who buys it, how it reaches them, what it earns, and what stops it.**

### 25.1 · The stakeholder map — and the blocker is never capability

| Role | Who | What they actually care about | What convinces them |
|---|---|---|---|
| **Sponsor / buyer** | NTRO — specifically whoever wrote SIH26147 | That the five requirements are met, and that the result is *theirs* | §4.8 (you read the theme tag), §18 (licence audit), §19 (air gap) |
| **Primary user** | The analyst doing this by hand today | Hours saved, and never being embarrassed by a confident wrong answer | §23 UX, §3.2 calibration, §23.2 the UNKNOWN screen |
| **Technical gatekeeper** | Whoever accredits software for a classified network | No egress, no unknown dependencies, reproducible build, readable source | §19.3 network-denied CI, SBOM, §18 |
| **Adjacent influencers** | DRDO/EW labs, BEL, C-DAC, DoT/WPC, ISRO ground segment, service SIGINT units, ECE departments | Whether it solves *their* version of the problem | §22 dual-use |
| **The real blocker** | Procurement and support | *"Who fixes this at 2 a.m., and which line item pays them?"* | §21.2 — the services contract **is** the line item, and MeitY's OSS policy backs it |

**Internalise the last row.** For government software, adoption is almost never killed by capability. It is
killed because nobody can name an owner and nobody can find a budget line for something that is free.
**Answer both before you are asked**, and you have already beaten most of the room on the axis they never
thought about.

### 25.2 · Market — sized honestly, which means not in rupees

**Resist the TAM slide.** There is no large Indian commercial market for blind SIGINT exploitation, any
number you put up would be invented, and an NTRO judge will know it instantly. Size it in **users and
capability**, and say out loud that you are deliberately not sizing it in revenue.

| Segment | Order of magnitude | Nature |
|---|---|---|
| National technical / SIGINT analysts (NTRO, service units, EW labs) | Hundreds to low thousands of seats | The sponsor. A **capability** market, not a revenue one |
| Spectrum regulation and enforcement (DoT / WPC monitoring) | Tens of stations, hundreds of users | Civil, unclassified, straightforwardly procurable |
| Space ground segment (ISRO, NewSpace operators) | Tens of organisations | §4.8 makes this native rather than an adaptation |
| Telecom and enterprise interference hunting | Hundreds of engineers | Commercial services revenue |
| Academic — ECE departments across India | Thousands of departments | Zero revenue. Enormous reach, and your recruitment pipeline (§21.2) |

Then reframe it, because this is both the honest argument and the stronger one:

> **The right measure is not what the market is worth. It is what *not having this* costs.** Today that is:
> every unanalysed capture in the archive; every analyst-hour spent on a signal a machine could have triaged;
> every new waveform that cannot be read until a foreign vendor decides to support it; and every petabyte
> stored because nothing can tell you which second of it mattered (§19.4). **None of those appear on a
> balance sheet. All of them are the actual cost, and all four are line items this tool removes.**

### 25.3 · Go-to-market — and the only ask that matters on stage

| Milestone | When | What happens | What you need |
|---|---|---|---|
| **M0 · Finale** | Day 0 | Working tool, corpus, public Apache-2.0 repo, attestation bundles for every demo file | Done by §17.4 |
| **M1 · Sponsor pilot** | 0–3 months | **Run it on the sponsor's own files, in the sponsor's own facility.** Nothing leaves. You bring a laptop | **Ten of their files.** That is the entire ask |
| **M2 · Accreditation + owner** | 3–6 months | Security review passes on the strength of §18/§19.3; offline installer; training deck; **one named institutional owner** with a faculty lead | An MoU. Costs nothing but signatures |
| **M3 · Second user + first contract** | 6–12 months | A civil user from §22 (WPC or a ground-segment group). Services listed on GeM. First paid support or cartridge-authoring contract | §21.2 |
| **M4 · Compounding** | 12–24 months | Cartridge library and corpus grow; papers published (§16.2, §4.4 track C); the tool outlives the founding team | §21.1 |

**The single most valuable outcome of the finale is not the prize. It is ten of the sponsor's own files.**
Everything else — accreditation, contracts, the corpus, the papers — follows from having been trusted with
real data once. Make that the explicit ask in your closing slide, because it is small, grantable, and
specific, where *"please adopt our tool"* is none of those things.

And make the offer that a confident team can make and a bluffing one cannot:

> **"Give us ten files and whatever you use on them today. Same files, same room, same afternoon. Compare
> the outputs — including where ours says it doesn't know."**

A bake-off is cheap, falsifiable, and it converts a pitch into a pilot. It is also the *only* honest use of
§3.2's calibration work, because calibration only means anything against someone else's ground truth.

### 25.4 · Unit economics

| Unit | Cost | Comparison |
|---|---|---|
| One capture analysed | Electricity plus amortised laptop — effectively **₹0** | Versus hours of a trained analyst, which is the PS's own opening complaint |
| One additional analyst seat | **₹0** | Versus per-seat negotiation with a foreign vendor |
| One additional waveform supported | **Hours of one analyst's time** writing a cartridge (§16.1) | Versus a vendor release cycle: months, or never |
| One additional deployment site | **₹0** — copy a folder (§23.3) | Versus licence, installation and vendor travel |
| One petabyte of archive indexed | Compute time on hardware already owned (§19.2 T4) | Versus not indexing it, which is the status quo |
| **The only real recurring cost** | **People** — support, cartridge authoring, training | Which is precisely what §21.2 sells, and precisely what a government can procure |

**The shape of this table is the business model.** Every marginal unit is free; all the cost is human
expertise. That is what makes free software commercially coherent and procurementally legal at the same time.

### 25.5 · IP strategy — publish, do not patent

A patent question will come, and the sophisticated answer is the opposite of the instinctive one:

| Option | Verdict |
|---|---|
| **Patent the method** | **No.** Years, real money, and useless against the actual competitors — a student team will not litigate against a foreign defence vendor, and the government user wants freedom to operate, not a toll gate. A patent also directly contradicts the strategic-control argument you are making in §18.2 |
| **Defensive publication** | **Yes, and do it early.** Publish the soft-syndrome test (§4.4 track C), the cartridge architecture (§16.1) and the identifiability ledger (§16.2) as papers or preprints. Published prior art means **nobody else can patent them and block India later.** This is protection *for* the sponsor, and it is free |
| **Trademark the name** | **Yes.** Cheap, fast, and the only IP that actually matters for an open project |
| **Keep the corpus and cartridge library as the asset** | **Yes.** Data and domain coverage are the moat (§26.3). Code is copyable; a growing, curated, India-specific library is not |

> *"We are not patenting it. We are publishing it — so that nobody else can patent it and charge India for
> it later."* That sentence lands with this sponsor in a way a patent-portfolio slide never will.

### 25.6 · Adoption risks — the business register, not the technical one

§11 covers what could break. This covers what could be built perfectly and still never used.

| Risk | Why it bites | Mitigation |
|---|---|---|
| **"Who supports it at 2 a.m.?"** | The single most common reason government pilots do not become deployments | Named institutional owner at M2; services contract at M3 (§21.2) |
| **Security accreditation stalls** | Unknown dependencies and network behaviour are disqualifying on a classified network | Already solved and *testable*: §19.3 no-egress CI, SBOM, pinned hashes, readable source (§18) |
| **The team graduates** | Eighteen months | §21.1 — the long tail is data, not code, so maintenance does not need the original engineers |
| **The analyst does not trust it** | One confident wrong answer ends adoption permanently | §3.2 calibration, §23.2 the UNKNOWN screen, §16.4 attestation. **This is why the honesty thesis is a commercial feature, not a virtue** |
| **Procurement has no line item for free software** | Real, and it kills more FOSS adoption than any technical factor | The contract is for *services*; MeitY's OSS policy explicitly frames "free" as freedom, not price (§18.2) |
| **The sponsor already has a foreign tool** | Likely | **Do not position as a replacement.** Position as a complement that goes where the foreign tool cannot: unknown waveforms, archive-scale batch, air-gapped sites, and anything they need to modify. Then offer the bake-off (§25.3) and let the result argue |
| **It gets classified and disappears** | A genuine risk for a good SIGINT tool | The cartridge boundary (§16.1) is the answer — the engine stays open and civilian, the sensitive coverage lives in cartridges the agency never publishes. **Design for this now; it is much harder to retrofit** |

---

## 26 · Why this idea stands out

Everything above is evidence. This is the summation — the slide the team should be able to deliver from
memory.

### 26.1 · Four kinds of competitor, four answers

| Competitor | What they bring | The answer, in one line |
|---|---|---|
| **Other SIH teams on SIH26147** — the real competition | URH + SigDigger + a RadioML-trained CNN, assembled in a weekend. Covers (i) and (ii) partly, (v) partly | *"Requirements three and four. And the benchmark they trained on doesn't vary symbol rate or roll-off — the exact quantities this PS asks us to measure"* (§21.3) |
| **Open-source tools** — URH, SigDigger, IQEngine, gr-inspector | Genuinely good demodulation, protocol labelling, visualisation | *"None of them reconstruct an interleaver or a code, and none of them can tell you when they are wrong"* (§8) |
| **Commercial incumbents** — Krypto500, W-CODE, CODE300-32 | Several hundred mature decoders. Better than you at coverage, today | *"They are ITAR-controlled and distributed through alliance channels India is not in. You cannot lawfully hand the manual to the analyst beside you. The constraint was never price"* (§20.1) |
| **The academic literature** | Code-aided synchronisation; blind code reconstruction | *"Two mature fields, adjacent for twenty years, and each one assumes the other's problem is already solved"* (§7) |

### 26.2 · The ten differentiators — each one checkable

Ordered by how hard they are to answer, not by how nice they sound.

| # | Differentiator | Why it cannot be waved away |
|---|---|---|
| 1 | **It closes the whole chain, samples to bits.** Requirements (i) through (v), in one tool | Most teams will reach (ii). Reaching (v) *requires* having solved (iii) and (iv) first — there is no shortcut and no partial credit |
| 2 | **Verification by resynthesis.** It rebuilds the waveform and shows you the difference | Every other tool reports a confidence number it cannot justify. This one produces a residual you can look at |
| 3 | **FEC is an instrument, not an obstacle.** The code certifies the physical layer to ~10⁻⁶ | §2.1 — and it is a known result (coded CRB below the non-data-aided bound), not a hopeful analogy |
| 4 | **Calibrated honesty.** UNKNOWN with a goodness-of-fit p-value, a reliability diagram, and capabilities that grey themselves out when the data is too short | §3.2, §3.6. **A tool that refuses is a tool an analyst can use.** Nobody else will demo a failure on purpose |
| 5 | **Identifiability shipped per field** — computed from the FIM, with a remediation hint | §16.2. The field reports accuracy against ground truth it generated itself, so the question never comes up |
| 6 | **Waveform cartridges.** Extension is a text file, not a code change — and it draws the open/classified boundary a government needs | §16.1. This is the answer to *"who maintains it in 2029"* and to *"can we add something we can't show you"* |
| 7 | **Attestation bundles.** `shruti verify` re-runs a finding to bit-identical output | §16.4. A finding another agency can check is a different category of object from an answer |
| 8 | **It read the theme tag.** Requirements (iii)–(v) are the CCSDS telemetry stack | §4.8. Nobody else will notice, and it is verifiable in thirty seconds by anyone who knows the standard |
| 9 | **₹0, open, air-gapped, and *proven* offline by a CI job that fails if a socket opens** | §18, §19. A testable security property, which almost no student project ships |
| 10 | **The blind Turing test.** A judge randomises the transmitter and reads their own sentence back out | §9 Act 3. **There is no partial-credit version.** No classifier-based team can attempt it at all |

### 26.3 · The moat — three time horizons

| Horizon | What a competitor could copy |
|---|---|
| **36 hours (the finale)** | **Nothing.** They can copy the *slides*. §7.4's argument holds: the intersection requires the inverse-problem reframe, DSP and autodiff in the same heads, coding theory over GF(2) in the same room, and a willingness to demo failure |
| **One term** | The twin, probably. A determined team with the right composition could rebuild the forward model and the library-match track |
| **Never, practically** | **The corpus** (§21.3 — no India-specific open RF corpus exists, and yours is generated by the twin so it compounds for free). **The cartridge library** — coverage is a long tail measured in analyst-years. **The institutional relationship** — the ten files, the MoU, the accreditation. **And the team composition itself**, which is the thing that was scarce to begin with |

**Note what the moat is made of.** Not algorithms — those get published (§25.5), deliberately. It is data,
coverage and relationships, all three of which get *stronger with use* and none of which can be forked.

### 26.4 · The positioning sentence

Everything compresses to this. If the team can say one thing when a judge asks *"why you?"* —

> **"Every other tool guesses what a signal is and reports a confidence score. We work out how to rebuild it,
> rebuild it, and show you the difference — and the proof that we got it right is that the error-correcting
> code decodes and the message comes out. It costs nothing, it runs air-gapped on a laptop, adding a new
> waveform is a text file instead of a foreign vendor, and it tells you when it doesn't know."**

Four clauses: **what it does differently**, **why that is proof rather than assertion**, **why a government
can actually deploy it**, and **why an analyst would trust it.** Novelty, rigour, feasibility and impact —
the four things being scored — in one breath.

---

## 27 · Additional edits to make in v1 (extends §13)

| Location | Action |
|---|---|
| §11 stack | **Remove `komm` (GPL-3.0).** Use `commpy` (BSD-3) + `galois` (MIT). Add the full audit of §18 |
| §11 stack | Add: GNU Radio as an **out-of-process** validation oracle only; never linked |
| §8 open-source table | Add **IQEngine (MIT)** — browser SigMF toolkit, and the most likely GUI fork for a competing team. Correct the `gr-inspector` link to [`gnuradio/gr-inspector`](https://github.com/gnuradio/gr-inspector) |
| §8 incumbent argument | Rebuild on **access, not price** — ITAR, no-trial, alliance-channel distribution (§20.1). This is the strongest version of the indigenisation case |
| §10.x impact | Add §20.2's cost table and §19.4's storage arithmetic. These are the numbers a non-technical evaluator will retain |
| §14 pitch spine | *"₹2,000 USB receiver"* → *"a ₹2,000-class USB dongle"*, and add the ₹0 file-only tier (§17.2) |
| §4 twin | Make the chain **cartridge-driven** from day one (§16.1). Retrofitting this later is expensive; doing it first costs nothing |
| §5 L6 SigMF schema | Add `shruti:identifiability` per field (§16.2) and `shruti:attestation` (§16.4) |
| §9 Act 3 | Add the sixth beat: a judge **edits a cartridge live** and SHRUTI decodes a waveform that did not exist ninety seconds earlier |
| §9 Act 4 | Add the air-gapped install, performed with the network cable pulled (§23.3) |
| §1 scorecard | Add two rows: **"Category: Software"** — the deliverable is a program that reads a file, nothing else (§17.2); and **"Theme: Space Technology"** — requirements (iii), (iv), (v) map onto CCSDS 131.0-B (§4.8). v1 and Part I both address neither |
| §5 L6 / build order | **Build the CCSDS cartridge first** (§4.8). One public, fully specified standard covers requirements (iii), (iv) and (v) simultaneously. Highest value per hour in the project |
| §12 build order | Insert CCSDS cartridge at step 4; it *is* track A's first target |
| §9 Acts | Every act **file-in, file-out, no radio on the critical path** (§9 preamble). Act 3 gains the hold-out-cartridge rebuttal; Act 5 becomes the CCSDS act |
| §11 risks | Add: *"demo depends on hardware working in the venue"* — severity **High**, mitigation: it doesn't (§9) |
| §3 loophole 15 / all citations | **Audit done (§7.5).** Two §4.5 citations were wrong and are replaced; one dead staging link replaced. **Re-run the audit the week before the finale**, and drop the IIT Madras attribution in §7.2 unless the author list is checked |
| **New slides** | Input-format support matrix and the test-oracle claim (§17.5) — a Software-track judge looks for these first; licence audit (§18); deployment ladder (§19.2); cost table (§20.2); sustainability (§21); dual-use (§22); **the ten differentiators and the positioning sentence (§26.2, §26.4)**; the plain-English slide (§24) |
| **Closing slide** | Make the ask concrete: **ten of the sponsor's own files, and a bake-off against whatever they use today** (§25.3). Not *"please adopt our tool"* |
| Repository, from commit 1 | `LICENSE` (Apache-2.0), `NOTICE`, CycloneDX SBOM in CI, the network-denied CI job (§19.3), `cartridges/` and `corpus/` under CC-BY-4.0 |

---

## 28 · Related documents

- [SHRUTI v1](SHRUTI-SIH26147.md) — the design this revises. Still the source for L0–L3, L5 self-exam, and the India-impact case
- [SIH26147 — plain-English problem explainer](SIH26147_RF_Signal_Analysis_Explained_Simply.md)
- [SIH26166 — Chandrayaan-2 alternative](SIH26166_Chandrayaan2_Explained_Simply.md)
- [PRAMANA — SIH26228](PRAMANA-SIH26228.md)











