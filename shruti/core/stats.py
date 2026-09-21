"""Statistics with distributions attached, not thresholds with vibes attached.

The single most important discipline in SHRUTI: **every verdict carries a
statistic whose null distribution is known**, so a refusal has a stated
false-rejection rate instead of a hand-tuned number.

Why a dB threshold on residual energy cannot work, at either end:

* **At low SNR** every hypothesis has a large residual, so the threshold rejects
  correct fits.
* **At high SNR** an arbitrarily small unmodelled impairment produces a residual
  that dwarfs the noise, so the threshold rejects correct fits *again*, for the
  opposite reason.

The fix is to normalise the residual by the noise variance the fit itself
estimated, compare against chi-squared, and add a model-error floor so that
high-SNR captures are tested against "noise + acknowledged model error" rather
than "noise alone".  The verdict then reads *"GoF p = 0.31 - residual consistent
with noise"* instead of *"-22.8 dB, trust us"*.
"""

from __future__ import annotations

from dataclasses import dataclass

import numpy as np
from scipy import stats as _st

__all__ = [
    "GoodnessOfFit",
    "goodness_of_fit",
    "binomial_bias_test",
    "whiteness_test",
    "os_cfar",
    "benjamini_hochberg",
    "reliability_diagram",
]


@dataclass
class GoodnessOfFit:
    """A calibrated verdict on whether a residual is consistent with noise."""

    statistic: float
    dof: int
    p_value: float
    residual_power: float
    noise_var: float
    model_error_floor: float

    @property
    def consistent_with_noise(self) -> bool:
        """True if we cannot reject the model at the 1% level."""
        return self.p_value > 0.01

    def verdict(self) -> str:
        if self.p_value > 0.05:
            return "residual consistent with noise"
        if self.p_value > 0.01:
            return "residual marginally consistent with noise"
        return "residual is NOT consistent with noise - model does not explain this signal"

    def plain_english(self) -> str:
        """The same conclusion for a non-specialist, which is half the room."""
        if self.p_value > 0.05:
            return "What is left over looks like noise, so nothing was missed."
        if self.p_value > 0.01:
            return "What is left over mostly looks like noise, but not cleanly."
        return "Something structured is left over - part of this signal is unexplained."

    def summary(self) -> str:
        return f"GoF p = {self.p_value:.3f} ({self.verdict()})"


def goodness_of_fit(
    residual: np.ndarray,
    noise_var: float,
    n_fitted_params: int = 0,
    model_error_floor: float = 0.02,
) -> GoodnessOfFit:
    """Chi-squared goodness of fit with an acknowledged model-error floor.

    `model_error_floor` is the fraction of signal power the twin admits it cannot
    reproduce - finite filter spans, quantisation, unmodelled front-end effects.
    Without it, a very high-SNR capture would be assessed against noise alone and
    every honest model would be rejected.
    """
    r = np.asarray(residual)
    n = r.size
    if n == 0:
        return GoodnessOfFit(0.0, 0, 1.0, 0.0, noise_var, model_error_floor)

    power = float(np.mean(np.abs(r) ** 2))
    effective_var = max(float(noise_var), 1e-30) * (1.0 + model_error_floor)

    # Complex residual: each sample contributes 2 real degrees of freedom.
    dof = max(1, 2 * n - n_fitted_params)
    stat = float(np.sum(np.abs(r) ** 2) / effective_var * 2.0)
    p = float(_st.chi2.sf(stat, dof))

    return GoodnessOfFit(
        statistic=stat,
        dof=dof,
        p_value=p,
        residual_power=power,
        noise_var=float(noise_var),
        model_error_floor=model_error_floor,
    )


def binomial_bias_test(successes: int, trials: int, p_null: float = 0.5) -> float:
    """Two-sided p-value that a syndrome is biased away from chance.

    **This is the L6 track C contribution in one function.**  Rank-based code
    reconstruction needs hard bits and degrades fast with errors.  Evaluating
    candidate parity checks on *soft* bits and testing the syndrome's bias
    against p = 0.5 extends the method several dB down in SNR - and yields a
    p-value rather than a threshold.

    A true parity check on a real codeword is satisfied far more often than
    chance; a spurious one is not.  With thousands of checks the p-value can
    reach astronomically small values, which is what a certificate is made of.
    """
    if trials <= 0:
        return 1.0
    return float(_st.binomtest(int(successes), int(trials), p_null).pvalue)


def benjamini_hochberg(pvalues: np.ndarray, fdr: float = 0.05) -> np.ndarray:
    """Benjamini-Hochberg FDR correction.  Returns a boolean "significant" mask.

    L6 sweeps a large hypothesis grid, so uncorrected p-values would produce
    false discoveries by the dozen.  FDR is the right correction here rather
    than Bonferroni: the tests are many and positively correlated, and we care
    about the proportion of false leads, not about never making one.
    """
    p = np.asarray(pvalues, dtype=float)
    n = len(p)
    if n == 0:
        return np.zeros(0, dtype=bool)
    order = np.argsort(p)
    ranked = p[order]
    thresh = fdr * (np.arange(1, n + 1) / n)
    below = ranked <= thresh
    out = np.zeros(n, dtype=bool)
    if below.any():
        cutoff = np.max(np.flatnonzero(below))
        out[order[: cutoff + 1]] = True
    return out


def whiteness_test(residual: np.ndarray, max_lag: int = 64) -> tuple[float, float]:
    """Ljung-Box test for remaining structure in a residual.

    **Size is not the only question.**  A small but *structured* residual is
    worse than a larger white one, because structure means a real emitter or a
    real modelling error is still in there.  Testing for it is what turns one
    residual into three products: a confidence, a buried-emitter detector, and a
    device fingerprint.
    """
    r = np.asarray(residual)
    r = r - np.mean(r)
    n = len(r)
    if n < max_lag * 4:
        max_lag = max(2, n // 4)
    if n < 16:
        return 0.0, 1.0

    denom = float(np.sum(np.abs(r) ** 2))
    if denom <= 0:
        return 0.0, 1.0

    q = 0.0
    for k in range(1, max_lag + 1):
        rk = float(np.abs(np.sum(r[k:] * np.conj(r[:-k]))) / denom)
        q += rk ** 2 / max(n - k, 1)
    q *= n * (n + 2)
    p = float(_st.chi2.sf(q, max_lag))
    return q, p


def os_cfar(
    power: np.ndarray,
    guard: int = 4,
    train: int = 16,
    rank: float = 0.75,
    pfa: float = 1e-4,
) -> tuple[np.ndarray, np.ndarray]:
    """Ordered-statistic CFAR detection.

    Returns ``(detections, threshold)``.  OS-CFAR rather than cell-averaging
    because the ordered statistic is robust when *other emitters* sit in the
    training cells - which in a wideband capture is the normal case, not the
    exception.  A magic threshold would have to be retuned for every band.
    """
    p = np.asarray(power, dtype=float)
    n = len(p)
    det = np.zeros(n, dtype=bool)
    thr = np.full(n, np.inf)
    half = guard + train
    if n < 2 * half + 1:
        return det, thr

    alpha = float(train) * (pfa ** (-1.0 / max(train, 1)) - 1.0)
    alpha = max(alpha, 1.0)

    for i in range(half, n - half):
        left = p[i - half : i - guard]
        right = p[i + guard + 1 : i + half + 1]
        ref = np.concatenate([left, right])
        if ref.size == 0:
            continue
        noise = float(np.quantile(ref, rank))
        t = alpha * noise
        thr[i] = t
        det[i] = p[i] > t
    return det, thr


def reliability_diagram(
    confidences: np.ndarray, correct: np.ndarray, bins: int = 10
) -> dict:
    """Calibration curve: when SHRUTI says 80%, is it right 80% of the time?

    The plot that turns "we are honest" from a claim into a measurement, and the
    one an analyst should be shown before being asked to trust anything.
    """
    c = np.asarray(confidences, dtype=float)
    y = np.asarray(correct, dtype=bool)
    edges = np.linspace(0.0, 1.0, bins + 1)
    idx = np.clip(np.digitize(c, edges) - 1, 0, bins - 1)

    centres, accuracy, counts = [], [], []
    for b in range(bins):
        m = idx == b
        counts.append(int(m.sum()))
        centres.append(float((edges[b] + edges[b + 1]) / 2))
        accuracy.append(float(y[m].mean()) if m.any() else float("nan"))

    valid = [i for i, n in enumerate(counts) if n > 0]
    ece = (
        float(np.sum([counts[i] * abs(accuracy[i] - centres[i]) for i in valid]) / max(len(c), 1))
        if valid else float("nan")
    )
    return {
        "bin_centres": centres,
        "accuracy": accuracy,
        "counts": counts,
        "expected_calibration_error": ece,
    }
