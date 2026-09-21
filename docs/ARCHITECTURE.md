# Architecture

```
L0  container + format inference     shruti/l0_container
L1  receiver self-model              shruti/l1_receiver
L2  wideband detection + tracking    shruti/l2_detect
L3  proposal short-list              shruti/l3_proposals
L4  the differentiable twin          shruti/l4_twin          ← the project
L4b iterative emitter peeling        shruti/l4b_peel
L5  soft demodulation                shruti/l5_demod
L6  interleaver + FEC                shruti/l6_fec
L7  bitstream structure              shruti/l7_bits
L8  GUI, SigMF, evidence             shruti/web, l8_report
         ▲                                    │
         └────── closure feedback ────────────┘
             decode outcome refines L4
```

Layers are **packages with enforced boundaries** — each importable, testable and
replaceable on its own, talking through typed dataclasses rather than a shared
blob. One dependency rule: nothing in `shruti.core` imports a layer; every layer
may import `shruti.core`.

Two boundaries carry the product's weight:

- **The cartridge interface** (`shruti/cartridge`) — a waveform crosses this line
  as *data*, never as code.
- **The twin's forward/inverse pair** (`shruti/l4_twin`) — everything depends on
  it; nothing it depends on depends back.

---

## The central idea

Conventional pipelines run one way — samples → parameters → symbols → bits, each
stage trusting the last — and report a confidence number they cannot justify.

SHRUTI runs the loop closed:

| Conventional | SHRUTI |
|---|---|
| FEC is the last obstacle before the payload | FEC is the **highest-precision instrument in the system** |
| Information flows one way | Information flows **both ways** |
| Decoding fails ⇒ give up | Decoding fails ⇒ **you know which estimate is wrong** |
| Confidence is a softmax or a residual in dB | Confidence is a **binomial test on parity checks** |

A rate-½ code means half the received bits are an exact algebraic constraint on
the other half. Those constraints are thousands of independent, noise-free tests
of whether *everything upstream* was estimated correctly. Staying symbol-aligned
across a 10⁵-symbol codeword requires `|ΔRs/Rs| < 10⁻⁶` — an order of magnitude
past what a cyclostationary estimator delivers, and **certified rather than
asserted**, because the code either decoded or it did not.

---

## Layer notes

### L0 · Container inference (`l0_container`)

Infers everything, asks for nothing. Every competing tool opens with a dialogue
requesting sample rate, dtype and centre frequency; refusing to is a visible
differentiator in the first ten seconds.

- `.wav`: **mono is not IQ.** An HF `.wav` is usually the real audio output of an
  SSB receiver — 300–3400 Hz of modem, no complex baseband, no RF centre
  frequency at all. Two channels may be true stereo *or* I-in-left/Q-in-right,
  decided by whether the spectrum is Hermitian (real signals are; IQ is not).
- Raw: dtype and endianness scored on DC balance, kurtosis and clipping.
- **Absolute sample rate is not identifiable from a headerless file.** Every
  measurable quantity is a ratio. Resolved from sidecars, six recorder filename
  conventions, or in-band anchors — and the *basis* is always reported.
- Memory mapped: files larger than RAM are normal, not an error.

### L3 · Proposals (`l3_proposals`)

Cheap physical-layer measurements first, so the expensive stages only run on
plausible hypotheses. Symbol rate from the cyclostationary line; modulation from
fourth-order cumulants and fit.

One deliberate subtlety: an M-PSK constellation *contains* every lower-order PSK
constellation, so 8-PSK always fits QPSK data. Ties break toward the simpler
hypothesis (Occam) and are settled for certain by whether the code decodes.

### L4 · The twin (`l4_twin`)

A parameterised generative model of a radio link. Renders `bits → FEC →
interleave → scramble → map → pulse-shape → channel → samples`, and the same
model inverted is the analysis.

- Nine modulations; RRC with recovered roll-off
- **Watterson HF channel** per ITU-R F.1487 — HF is the primary band of
  interest, and without a real ionospheric model a faded capture produces a
  large residual and the honesty mechanism misfires on it
- **One parameter set renders both `.IQ` and `.wav`** (`ssb.py`). The spectral
  relationship between the two formats is a derivable transform, not something
  learned from paired data

### L5 · Soft demodulation (`l5_demod`)

Emits **log-likelihood ratios, not hard bits** — every L6 track works
dramatically better on soft information, and this single choice is where most
implementations lose their FEC stage.

The standing ambiguities — phase rotation, spectral inversion, differential vs
absolute encoding, symbol alignment — are **enumerated, not guessed**. Each is
small-cardinality, and all are resolved the same way: by which one lets the code
decode. Where a conventional tool needs a human to flip a switch and listen, this
is a binomial test.

### L6 · Interleaver and FEC (`l6_fec`)

The structural fact that makes this tractable:

> An interleaver is a permutation, a permutation is linear over GF(2), and a
> linear code composed with a permutation is still a linear code. So the
> interleaver-and-FEC composite is **one linear map**, and its dual space is
> recoverable by linear algebra on the bits.

All four interleaver families are one mechanism differing only in the *pattern*
of syndrome failures. All four FEC families are implemented.

| Track | Method | Covers |
|---|---|---|
| **A** library match | test against cartridge specs | most real traffic; fast and decisive |
| **B** algebraic | rank-deficiency / dual-code search | unknown codes, given 10⁴–10⁶ bits |
| **C** soft-syndrome | binomial test on soft bits | extends B several dB down in SNR |

**Never let B block A.** Track A is a week of work and covers most traffic;
B and C are research. That ordering is the project's central risk control.

Scoring uses **re-encode agreement**: decode, re-encode, and measure what
fraction of the received stream is reproduced. The right code gives ≈1.0; a
wrong one lands near 0.87 (the covering radius of a rate-½ code). A Viterbi path
metric cannot do this job — it scales with LLR magnitude, so a confidently-wrong
hypothesis outscores a tentatively-right one.

### L7 · Bitstream structure (`l7_bits`)

Frame-structure recovery needs no machine learning. Fold the stream at the frame
period and take per-column entropy: low-entropy columns are sync words,
addresses and padding; high-entropy columns are payload. **That profile *is* the
segmentation.**

Frame period detection insists on the harmonic *comb*, then reduces to the
fundamental — a frame of length P correlates just as strongly at 2P and 3P, and
reporting 2P silently halves the frame count and mangles every field boundary.

---

## Honesty engineering

Three mechanisms, because a tool that is confidently wrong once is never trusted
again:

1. **A χ² goodness-of-fit statistic, not a dB threshold.** A dB threshold fails
   at both ends — at low SNR every hypothesis has a large residual, and at high
   SNR any unmodelled impairment dwarfs the noise. Normalising by the fit's own
   noise estimate, with an acknowledged model-error floor, gives a verdict with
   a stated false-rejection rate.
2. **Residual structure, not just size.** A small but *structured* residual is
   worse than a larger white one. Whiteness testing turns one residual into
   three products: calibrated confidence, buried-emitter detection, and a device
   fingerprint.
3. **Data-sufficiency gates.** Each capability declares its bit requirement and
   greys itself out with the reason. Every implementation that skips this will
   attempt FEC identification on a 4 ms burst and produce confident nonsense.

---

## Bugs worth knowing about

Each of these passed casual testing and was wrong. They are recorded because
the failure modes are instructive, and all are covered by regression tests.

| Bug | Symptom | Why it survives casual testing |
|---|---|---|
| Puncturing tail truncation | Rates 3/4 and 7/8 only | 1/2 and 2/3 are fine |
| LDPC weight-0 columns | Error floor, not failure | Looks like a noisy channel |
| RRC cascade delay counted once | Perfect constellation, garbage bits | EVM says everything is fine |
| QPSK phase reference assumed 0 | Same | Conventional QPSK sits at ±45° |
| CCSDS RS interleaving modelled bit-wise | Payload appears, certificate declines | RS is systematic, so text still shows |
| CFO estimator subtracted the mean | Fails **only** near zero offset | Testing uses large artificial offsets |
| Conv decode with `terminated=True` | ~8% residual BER | A capture ends where recording stopped |
| Interleaver pass-through tail | Errors begin at an exact period multiple | Only bites when a later stage changes length |
| Sync assumed at offset 0 | Length-dependent failures | Synthetic captures start frame-aligned |
| FSK timing by tone margin | Flat metric, noise picks the alignment | Works on clean signals |

The fifth is the one the design predicted: the payload appeared while the
certificate refused. **That is precisely what the certificate is for.**
