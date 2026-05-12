# -*- coding: utf-8 -*-
"""
Distribution Fitting Tool: Input Analysis with Desk-DistFit
============================================================
`desk-distfit` is the official DESK input-analysis CLI for
statistically fitting probability distributions to empirical data.

DESK adopts a verb-oriented command-line interface, where simulation
tasks are expressed as structured actions (`desk-distfit`),
ensuring consistency, reproducibility, and ease of learning across
the framework. Fit probability distributions to empirical data.

Author: João Flávio F. Almeida (PPGEP-UFMG) <joao.flavio@dep.ufmg.br>
Course: EPD899: Simulating Logistics Systems

═══════════════════════════════════════════════════════════════
SCIPY → PYTHON RANDOM MODULE: PARAMETER TRANSLATION REFERENCE
═══════════════════════════════════════════════════════════════

Every scipy distribution is fit as (shape_params..., loc, scale).
Python's `random` module uses different parameterizations. The
correct translations are:

  expon:       scipy(loc, scale)       → expovariate(1/scale)
                                          [+ loc if loc is significant]
  norm:        scipy(loc, scale)       → gauss(loc, scale)
  lognorm:     scipy(s, loc, scale)    → lognormvariate(ln(scale), s)
                 s=sigma, scale=exp(mu)  [loc shift NOT supported natively]
  triang:      scipy(c, loc, scale)    → triangular(loc, loc+scale, loc+c*scale)
  beta:        scipy(a, b, loc, scale) → loc + scale * betavariate(a, b)
                 [loc/scale define the support interval]
  gamma:       scipy(a, loc, scale)    → gammavariate(a, scale)
                 scale=beta (NOT 1/scale!)
  weibull_min: scipy(c, loc, scale)    → weibullvariate(scale, c)
                 c=beta(shape), scale=alpha
  weibull_max: scipy(c, loc, scale)    → weibullvariate(scale, c)  [reflected]
  uniform:     scipy(loc, scale)       → uniform(loc, loc+scale)
"""

import math
import warnings
from pathlib import Path
from typing import List, Tuple, Optional, Union
import logging
import argparse
import sys

import numpy as np
import pandas as pd
import scipy.stats as st
import matplotlib.pyplot as plt
from dataclasses import dataclass

# Configure logging
logging.basicConfig(level=logging.INFO, format='%(levelname)s: %(message)s')
logger = logging.getLogger(__name__)

# Configure matplotlib
plt.style.use('ggplot')
plt.rcParams['figure.figsize'] = (10, 7)
plt.rcParams['font.size'] = 11

# If |loc| > this fraction of the mean, include it in the Python expression.
# Below this threshold loc is treated as negligible floating-point noise.
_LOC_SIGNIFICANCE_RATIO = 0.01


@dataclass
class DistributionResult:
    """Data class to store distribution fitting results."""
    name: str
    statistic: float
    p_value: float
    parameters: Tuple
    sse: float = None
    is_significant: bool = None


# ─────────────────────────────────────────────────────────────
# Translation helpers  (scipy params → Python random module)
# ─────────────────────────────────────────────────────────────

def _loc_is_significant(loc: float, data_mean: float) -> bool:
    """Return True if loc shift is large enough to matter."""
    if data_mean == 0:
        return abs(loc) > 1e-9
    return abs(loc / data_mean) > _LOC_SIGNIFICANCE_RATIO


def _translate_expon(loc: float, scale: float, data_mean: float) -> str:
    """
    scipy expon(loc, scale): mean = loc + scale
    Python: expovariate(lambda) where lambda = 1/scale, samples from 0.
    When loc is significant, prepend it as an additive shift.
    """
    rate = 1.0 / scale
    base = f"random.expovariate({rate:.6g})"
    if _loc_is_significant(loc, data_mean):
        return f"{loc:.6g} + {base}  # loc shift: minimum value ≈ {loc:.4g}"
    return base


def _translate_norm(loc: float, scale: float) -> str:
    """scipy norm(loc, scale) == gauss(mu, sigma). Direct 1-to-1 mapping."""
    return f"random.gauss({loc:.6g}, {scale:.6g})"


def _translate_lognorm(s: float, loc: float, scale: float, data_mean: float) -> str:
    """
    scipy lognorm(s, loc, scale):
      s     = sigma  (log-space std dev)
      scale = exp(mu) → mu = ln(scale)
      loc   = additive shift (usually 0 for non-negative data)

    Python lognormvariate(mu, sigma):
      mu    = log-space mean  = ln(scale)
      sigma = log-space std   = s

    ⚠ Python's lognormvariate does NOT support a loc shift.
    If loc ≠ 0 the expression becomes: loc + lognormvariate(mu, sigma)
    """
    mu = math.log(scale)  # correct conversion: mu = ln(scale)
    base = f"random.lognormvariate({mu:.6g}, {s:.6g})"
    if _loc_is_significant(loc, data_mean):
        return f"{loc:.6g} + {base}  # loc shift applied; consider refitting with floc=0"
    return base


def _translate_triang(c: float, loc: float, scale: float) -> str:
    """
    scipy triang(c, loc, scale):
      low  = loc
      high = loc + scale
      mode = loc + c * scale

    Python triangular(low, high, mode): direct mapping.
    """
    low  = loc
    high = loc + scale
    mode = loc + c * scale
    return f"random.triangular({low:.6g}, {high:.6g}, {mode:.6g})"


def _translate_beta(a: float, b: float, loc: float, scale: float) -> str:
    """
    scipy beta(a, b, loc, scale): samples on [loc, loc+scale].
    Python betavariate(a, b): samples on [0, 1].

    ⚠ loc and scale MUST be included — dropping them silently
    produces samples on [0, 1] regardless of the fitted support.

    Correct expression: loc + scale * random.betavariate(a, b)
    """
    inner = f"random.betavariate({a:.6g}, {b:.6g})"
    if abs(loc) < 1e-9 and abs(scale - 1.0) < 1e-9:
        return inner
    return f"{loc:.6g} + {scale:.6g} * {inner}"


def _translate_gamma(a: float, loc: float, scale: float, data_mean: float) -> str:
    """
    scipy gamma(a, loc, scale): mean = loc + a * scale, scale = beta.
    Python gammavariate(alpha, beta): mean = alpha * beta, beta = scale.

    ⚠ beta = scale  (NOT 1/scale — that would be the rate parameterization).
    """
    base = f"random.gammavariate({a:.6g}, {scale:.6g})"
    if _loc_is_significant(loc, data_mean):
        return f"{loc:.6g} + {base}  # loc shift applied"
    return base


def _translate_weibull_min(c: float, loc: float, scale: float, data_mean: float) -> str:
    """
    scipy weibull_min(c, loc, scale):
      c     = shape = beta
      scale = alpha  (characteristic life)
      loc   = shift (usually 0)

    Python weibullvariate(alpha, beta):
      alpha = scale  (NOT loc!)
      beta  = c      (shape, NOT loc!)

    ⚠ The original code used loc as beta — always near 0, completely wrong.
    """
    base = f"random.weibullvariate({scale:.6g}, {c:.6g})"
    if _loc_is_significant(loc, data_mean):
        return f"{loc:.6g} + {base}  # loc shift applied"
    return base


def _translate_weibull_max(c: float, loc: float, scale: float, data_mean: float) -> str:
    """
    scipy weibull_max is the reflected (maximum) Weibull.
    Python's weibullvariate generates the minimum Weibull only.
    We include a note and use the same alpha/beta mapping.
    """
    base = f"random.weibullvariate({scale:.6g}, {c:.6g})"
    note = "  # weibull_max: negate if you need the reflected variant"
    if _loc_is_significant(loc, data_mean):
        return f"{loc:.6g} + {base}{note}"
    return base + note


def _translate_uniform(loc: float, scale: float) -> str:
    """
    scipy uniform(loc, scale): samples on [loc, loc+scale].
    Python uniform(a, b): samples on [a, b]. Direct mapping.
    """
    return f"random.uniform({loc:.6g}, {loc + scale:.6g})"


# ─────────────────────────────────────────────────────────────
# Main fitter class
# ─────────────────────────────────────────────────────────────

class DistributionFitter:
    """
    Fit probability distributions to empirical data and translate
    the fitted parameters to Python's `random` module expressions.
    """

    DEFAULT_DISTRIBUTIONS = [
        'uniform', 'triang', 'expon', 'norm', 'lognorm',
        'beta', 'gamma', 'weibull_min', 'weibull_max'
    ]

    # Distributions that are naturally ≥ 0: fix loc=0 during fitting
    # unless the user's data has negative values.
    _NONNEG_DISTRIBUTIONS = {'expon', 'lognorm', 'gamma', 'weibull_min', 'weibull_max'}

    def __init__(self, alpha: float = 0.05, bins: int = 50,
                 force_loc_zero: bool = True,
                 max_sample_size: int = 2000):
        """
        Args:
            alpha:           Significance level for KS test.
            bins:            Histogram bins for SSE calculation and plots.
            force_loc_zero:  If True (default), fit non-negative distributions
                             with floc=0.
            max_sample_size: When the dataset exceeds this size, a stratified
                             random subsample is drawn for fitting and the KS
                             test so the test remains meaningful (default: 2000).
                             Set to 0 or None to disable subsampling.
        """
        self.alpha = alpha
        self.bins = bins
        self.force_loc_zero = force_loc_zero
        self.max_sample_size = max_sample_size or 0
        self.results: List[DistributionResult] = []
        self.data: Optional[pd.Series] = None       # full dataset (plots / stats)
        self._fit_data: Optional[pd.Series] = None  # subsample used for fitting
        self._was_sampled: bool = False

    # ── Data loading ──────────────────────────────────────────

    def load_data(self, filepath: Union[str, Path]) -> pd.Series:
        """Load one numeric value per line from a plain-text file."""
        filepath = Path(filepath)
        if not filepath.exists():
            raise FileNotFoundError(f"File not found: {filepath}")
        with open(filepath, 'r', encoding='utf-8') as f:
            values = [float(line.strip()) for line in f if line.strip()]
        self.data = pd.Series(values, name='data')
        logger.info(f"Loaded {len(self.data)} data points from {filepath}")
        return self.data

    def set_data(self, data: Union[list, np.ndarray, pd.Series]) -> pd.Series:
        self.data = pd.Series(data, name='data')
        logger.info(f"Set {len(self.data)} data points")
        return self.data

    def _prepare_fit_data(self) -> pd.Series:
        """
        Return the data series used for fitting and KS testing.

        When len(data) > max_sample_size, draw a stratified random subsample
        by percentile rank so the shape of the distribution is preserved.
        The full dataset is still used for summary statistics and plots.
        """
        n = len(self.data)
        if self.max_sample_size and n > self.max_sample_size:
            # Stratified sample: sort by value, take evenly-spaced indices.
            # This preserves the empirical distribution shape better than
            # a pure random draw, especially for heavy-tailed data.
            sorted_idx = np.argsort(self.data.values)
            step = n / self.max_sample_size
            chosen = sorted_idx[
                np.round(np.arange(self.max_sample_size) * step).astype(int)
            ]
            # Shuffle so KS test ordering is randomised
            rng = np.random.default_rng(seed=42)
            rng.shuffle(chosen)
            self._fit_data = self.data.iloc[chosen].reset_index(drop=True)
            self._was_sampled = True
            logger.info(
                f"Subsampled {n:,} → {self.max_sample_size:,} observations for fitting."
            )
        else:
            self._fit_data = self.data
            self._was_sampled = False
        return self._fit_data

    # ── Parameter names ───────────────────────────────────────

    @staticmethod
    def get_parameter_names(distribution: Union[str, st.rv_continuous]) -> List[str]:
        if isinstance(distribution, str):
            distribution = getattr(st, distribution)
        params = []
        if distribution.shapes:
            params = [n.strip() for n in distribution.shapes.split(',')]
        if distribution.name in st._continuous_distns._distn_names:
            params += ['loc', 'scale']
        elif distribution.name in st._discrete_distns._distn_names:
            params += ['loc']
        return params

    # ── Fitting ───────────────────────────────────────────────

    def _fit_single(self, dist_name: str, dist) -> Tuple:
        """Return params from dist.fit(), respecting force_loc_zero."""
        data_min = self._fit_data.min()
        use_floc0 = (
            self.force_loc_zero
            and dist_name in self._NONNEG_DISTRIBUTIONS
            and data_min >= 0
        )
        with warnings.catch_warnings():
            warnings.filterwarnings('ignore')
            if use_floc0:
                return dist.fit(self._fit_data, floc=0)
            return dist.fit(self._fit_data)

    def fit_distributions(self, distributions: Optional[List[str]] = None) -> List[DistributionResult]:
        """
        Fit all requested distributions, run KS test, compute SSE.
        Results are sorted by p-value (descending).
        """
        if self.data is None:
            raise ValueError("No data loaded. Call load_data() or set_data() first.")

        self._prepare_fit_data()
        distributions = distributions or self.DEFAULT_DISTRIBUTIONS
        self.results = []

        y_hist, x_edges = np.histogram(self._fit_data, bins=self.bins, density=True)
        x_mid = (x_edges[:-1] + x_edges[1:]) / 2.0

        print(f"\n{'#':<4} {'Distribution':<15} {'KS stat':<10} {'p-value':<10} {'SSE':<12} {'Pass α'}")
        print("─" * 62)

        for i, dist_name in enumerate(distributions):
            try:
                dist = getattr(st, dist_name)
                params = self._fit_single(dist_name, dist)

                ks_stat, p_value = st.kstest(self._fit_data, dist_name, params)

                arg = params[:-2] if len(params) > 2 else []
                loc, scale = params[-2], params[-1]
                with warnings.catch_warnings():
                    warnings.filterwarnings('ignore', category=RuntimeWarning)
                    pdf_vals = dist.pdf(x_mid, *arg, loc=loc, scale=scale)
                sse = float(np.sum((y_hist - pdf_vals) ** 2))

                is_sig = p_value >= self.alpha
                result = DistributionResult(
                    name=dist_name,
                    statistic=ks_stat,
                    p_value=p_value,
                    parameters=params,
                    sse=sse,
                    is_significant=is_sig
                )
                self.results.append(result)

                mark = " ✓" if is_sig else ""
                print(f"{i+1:<4} {dist_name:<15} {ks_stat:<10.4f} {p_value:<10.4f} {sse:<12.6f}{mark}")

            except Exception as e:
                logger.warning(f"Could not fit {dist_name}: {e}")

        self.results.sort(key=lambda r: r.p_value, reverse=True)
        logger.info(f"Fitted {len(self.results)} distributions.")
        return self.results

    def get_best_fit(self) -> Optional[DistributionResult]:
        return self.results[0] if self.results else None

    # ── Translation: scipy → Python random ───────────────────

    def get_python_random_code(self, result: DistributionResult) -> str:
        """
        Translate scipy fitted parameters into a Python `random` module
        expression. Each distribution has a dedicated translator that
        applies the correct mathematical mapping (see module docstring).
        """
        name   = result.name
        params = result.parameters
        pnames = self.get_parameter_names(name)
        pd_    = dict(zip(pnames, params))

        loc   = pd_.get('loc', 0.0)
        scale = pd_.get('scale', 1.0)
        mean  = float(self.data.mean()) if self.data is not None else 1.0

        try:
            if name == 'expon':
                return _translate_expon(loc, scale, mean)

            elif name == 'norm':
                return _translate_norm(loc, scale)

            elif name == 'lognorm':
                # scipy lognorm shape param is named 's'
                return _translate_lognorm(pd_['s'], loc, scale, mean)

            elif name == 'triang':
                return _translate_triang(pd_['c'], loc, scale)

            elif name == 'beta':
                return _translate_beta(pd_['a'], pd_['b'], loc, scale)

            elif name == 'gamma':
                return _translate_gamma(pd_['a'], loc, scale, mean)

            elif name == 'weibull_min':
                return _translate_weibull_min(pd_['c'], loc, scale, mean)

            elif name == 'weibull_max':
                return _translate_weibull_max(pd_['c'], loc, scale, mean)

            elif name == 'uniform':
                return _translate_uniform(loc, scale)

        except KeyError as e:
            logger.error(f"Missing parameter {e} for {name}")

        return f"# No Python random translation available for '{name}'"

    # ── Reporting ─────────────────────────────────────────────

    def print_parameters(self) -> None:
        """Print raw scipy parameters for every fitted distribution."""
        if not self.results:
            logger.warning("No results. Run fit_distributions() first.")
            return
        print("\nFitted Parameters (scipy notation):")
        print("=" * 70)
        for r in self.results:
            pnames = self.get_parameter_names(r.name)
            pairs  = ", ".join(f"{k}={v:.6g}" for k, v in zip(pnames, r.parameters))
            print(f"\n  {r.name:15s} p={r.p_value:.4f}  [{pairs}]")
            print(f"  {'→ python:':<15} {self.get_python_random_code(r)}")

    def generate_summary_report(self) -> str:
        if not self.results:
            return "No results. Run fit_distributions() first."

        best = self.get_best_fit()
        pnames = self.get_parameter_names(best.name)
        param_str = ", ".join(f"{k}={v:.4g}" for k, v in zip(pnames, best.parameters))
        python_code = self.get_python_random_code(best)

        lines = [
            "",
            "Distribution Fitting Summary Report",
            "=" * 60,
            "",
            "Data Statistics:",
            f"  N        = {len(self.data)}",
            f"  Mean     = {self.data.mean():.4f}",
            f"  Std Dev  = {self.data.std():.4f}",
            f"  CV       = {self.data.std()/self.data.mean():.4f}",
            f"  Skewness = {float(self.data.skew()):.4f}",
            f"  Min      = {self.data.min():.4f}",
            f"  Max      = {self.data.max():.4f}",
        ]
        if self._was_sampled:
            lines.append(
                f"  (Fitting used a stratified sample of {len(self._fit_data):,} "
                f"from {len(self.data):,} observations)"
            )
        lines += [
            "",
            f"Best Fitting Distribution: {best.name}",
            f"  scipy params : {param_str}",
            f"  KS statistic : {best.statistic:.4f}",
            f"  p-value      : {best.p_value:.4f}",
            f"  Significant  : {'Yes ✓' if best.is_significant else 'No ✗'}  (α={self.alpha})",
            "",
            "Python random code (copy-paste ready):",
            f"  {python_code}",
            "",
            "Top 5 by p-value:",
        ]
        for i, r in enumerate(self.results[:5], 1):
            sig = "✓" if r.is_significant else "✗"
            code = self.get_python_random_code(r)
            lines.append(f"  {i}. {r.name:<15} p={r.p_value:.4f} {sig}  →  {code}")

        return "\n".join(lines)

    # ── Plotting ──────────────────────────────────────────────

    def plot_results(self, show_all: bool = False, figsize: Tuple = (16, 5)) -> None:
        if not self.results or self.data is None:
            logger.warning("Nothing to plot.")
            return

        best = self.get_best_fit()
        results_to_plot = self.results[:5] if show_all else [best]

        # ── palette & style ──────────────────────────────────
        PALETTE   = ['#2563EB', '#DC2626', '#16A34A', '#D97706', '#7C3AED',
                     '#0891B2', '#BE185D', '#65A30D', '#EA580C', '#6366F1']
        BG        = '#F8FAFC'
        GRID_CLR  = '#CBD5E1'
        DATA_CLR  = '#94A3B8'
        DATA_EDGE = '#64748B'
        TITLE_CLR = '#0F172A'
        LABEL_CLR = '#334155'

        fig, axes = plt.subplots(1, 3, figsize=figsize)
        fig.patch.set_facecolor(BG)
        for ax in axes:
            ax.set_facecolor(BG)
            ax.tick_params(colors=LABEL_CLR, labelsize=9)
            for spine in ax.spines.values():
                spine.set_edgecolor(GRID_CLR)
            ax.grid(True, color=GRID_CLR, linewidth=0.6, alpha=0.8)

        x_min, x_max = self.data.min(), self.data.max()
        pad   = 0.08 * (x_max - x_min)
        x_rng = np.linspace(max(0, x_min - pad), x_max + pad, 1000)

        # ── Panel 1: Data Histogram (full dataset) ───────────
        ax1 = axes[0]
        counts, edges, _ = ax1.hist(
            self.data, bins=self.bins, density=True,
            color=DATA_CLR, edgecolor=DATA_EDGE, linewidth=0.3, alpha=0.85,
            label='Empirical data'
        )
        ax1.set_title("Data Distribution", fontsize=11, fontweight='bold',
                      color=TITLE_CLR, pad=10)
        ax1.set_xlabel("Value", fontsize=9, color=LABEL_CLR)
        ax1.set_ylabel("Density", fontsize=9, color=LABEL_CLR)
        # Annotate basic stats
        mu, sd = self.data.mean(), self.data.std()
        ax1.axvline(mu, color='#0F172A', linewidth=1.2, linestyle='--', alpha=0.7,
                    label=f'Mean = {mu:.2f}')
        ax1.legend(fontsize=8, framealpha=0.9, edgecolor=GRID_CLR)
        sample_note = (
            f"N = {len(self.data):,}"
            + (f"  (fit on {len(self._fit_data):,})" if self._was_sampled else "")
        )
        ax1.text(0.97, 0.97, sample_note, transform=ax1.transAxes,
                 fontsize=7.5, color=LABEL_CLR, va='top', ha='right',
                 bbox=dict(boxstyle='round,pad=0.3', fc=BG, ec=GRID_CLR, alpha=0.9))

        # ── Panel 2: PDF Overlay (fitted curves) ─────────────
        ax2 = axes[1]
        ax2.hist(
            self.data, bins=self.bins, density=True,
            color=DATA_CLR, edgecolor=DATA_EDGE, linewidth=0.3, alpha=0.5,
            label='Data'
        )
        for idx, r in enumerate(results_to_plot):
            try:
                dist = getattr(st, r.name)
                arg  = r.parameters[:-2] if len(r.parameters) > 2 else []
                loc, scale = r.parameters[-2], r.parameters[-1]
                with warnings.catch_warnings():
                    warnings.filterwarnings('ignore', category=RuntimeWarning)
                    y = dist.pdf(x_rng, *arg, loc=loc, scale=scale)
                y = np.where(np.isfinite(y), y, np.nan)
                lw    = 2.2 if idx == 0 else 1.4
                alpha = 1.0 if idx == 0 else 0.65
                label = f"{r.name}  (p={r.p_value:.3f}{'✓' if r.is_significant else ''})"
                ax2.plot(x_rng, y, lw=lw, color=PALETTE[idx % len(PALETTE)],
                         alpha=alpha, label=label)
            except Exception as e:
                logger.warning(f"PDF plot error for {r.name}: {e}")

        python_code = self.get_python_random_code(best)
        ax2.set_title(f"PDF Fit  —  {best.name}\n{python_code}",
                      fontsize=10, fontweight='bold', color=TITLE_CLR, pad=10)
        ax2.set_xlabel("Value", fontsize=9, color=LABEL_CLR)
        ax2.set_ylabel("Density", fontsize=9, color=LABEL_CLR)
        ax2.legend(fontsize=8, framealpha=0.9, edgecolor=GRID_CLR)

        # ── Panel 3: Empirical CDF vs Theoretical CDF ────────
        ax3 = axes[2]
        sorted_data = np.sort(self.data.values)
        ecdf_y = np.arange(1, len(sorted_data) + 1) / len(sorted_data)
        ax3.plot(sorted_data, ecdf_y, color=DATA_CLR, linewidth=1.2,
                 alpha=0.85, label='Empirical CDF', zorder=2)

        for idx, r in enumerate(results_to_plot):
            try:
                dist  = getattr(st, r.name)
                arg   = r.parameters[:-2] if len(r.parameters) > 2 else []
                loc, scale = r.parameters[-2], r.parameters[-1]
                with warnings.catch_warnings():
                    warnings.filterwarnings('ignore', category=RuntimeWarning)
                    cdf_y = dist.cdf(x_rng, *arg, loc=loc, scale=scale)
                cdf_y = np.where(np.isfinite(cdf_y), cdf_y, np.nan)
                lw    = 2.2 if idx == 0 else 1.4
                alpha = 1.0 if idx == 0 else 0.65
                label = f"{r.name}  D={r.statistic:.4f}"
                ax3.plot(x_rng, cdf_y, lw=lw, color=PALETTE[idx % len(PALETTE)],
                         alpha=alpha, label=label, zorder=3)
            except Exception as e:
                logger.warning(f"CDF plot error for {r.name}: {e}")

        # Shade the KS gap for the best fit
        try:
            dist  = getattr(st, best.name)
            arg   = best.parameters[:-2] if len(best.parameters) > 2 else []
            loc, scale = best.parameters[-2], best.parameters[-1]
            with warnings.catch_warnings():
                warnings.filterwarnings('ignore', category=RuntimeWarning)
                cdf_at_data = dist.cdf(sorted_data, *arg, loc=loc, scale=scale)
            cdf_at_data = np.where(np.isfinite(cdf_at_data), cdf_at_data, np.nan)
            diffs = np.abs(ecdf_y - cdf_at_data)
            k_idx = int(np.argmax(diffs))
            x_ks  = sorted_data[k_idx]
            y_emp = ecdf_y[k_idx]
            y_th  = cdf_at_data[k_idx]
            ax3.plot([x_ks, x_ks], [y_emp, y_th],
                     color='#DC2626', linewidth=2, linestyle='--',
                     zorder=4, label=f'Max D = {best.statistic:.4f}')
            ax3.scatter([x_ks], [(y_emp + y_th) / 2], color='#DC2626',
                        s=40, zorder=5)
        except Exception:
            pass

        ax3.set_title("Empirical vs Theoretical CDF", fontsize=11,
                      fontweight='bold', color=TITLE_CLR, pad=10)
        ax3.set_xlabel("Value", fontsize=9, color=LABEL_CLR)
        ax3.set_ylabel("Cumulative Probability", fontsize=9, color=LABEL_CLR)
        ax3.set_ylim(0, 1.02)
        ax3.legend(fontsize=8, framealpha=0.9, edgecolor=GRID_CLR)

        # ── Final layout ──────────────────────────────────────
        sig_str = "✓ Significant" if best.is_significant else "✗ Not significant"
        fig.suptitle(
            f"Distribution Fitting  ·  Best fit: {best.name}  "
            f"(KS D={best.statistic:.4f},  p={best.p_value:.4f},  {sig_str})",
            fontsize=12, fontweight='bold', color=TITLE_CLR, y=0.98
        )
        plt.tight_layout()
        plt.show()


# ─────────────────────────────────────────────────────────────
# CLI
# ─────────────────────────────────────────────────────────────

def resolve_data_path(data_arg: str) -> Path:
    """Resolve data file path relative to cwd or as absolute."""
    path = Path(data_arg).expanduser()
    if path.is_absolute() and path.exists():
        return path.resolve()
    cwd_path = Path.cwd() / path
    if cwd_path.exists():
        return cwd_path.resolve()
    raise FileNotFoundError(
        f"Data file not found: '{data_arg}'\n"
        f"  Tried: {cwd_path}\n"
        f"  Tried: {path.resolve()}"
    )


def create_argument_parser() -> argparse.ArgumentParser:
    parser = argparse.ArgumentParser(
        description="DESK – Distribution Fitting Tool (desk-distfit)",
        formatter_class=argparse.RawDescriptionHelpFormatter,
        epilog="""
Examples:
  desk-distfit -d data/arrivals.txt
  desk-distfit -d data/arrivals.txt -a 0.01 -b 100
  desk-distfit -d data/arrivals.txt --no-plot
  desk-distfit -d data/arrivals.txt --show-all
  desk-distfit -d data/arrivals.txt --distributions norm expon lognorm
  desk-distfit -d data/arrivals.txt -o results.json --format json
  desk-distfit -d data/arrivals.txt --no-floc0   # allow loc≠0 for all dists
  desk-distfit -d data/arrivals.txt --max-sample 5000  # larger subsample
  desk-distfit -d data/arrivals.txt --max-sample 0     # fit on full dataset
        """
    )
    parser.add_argument('-d', '--data',    required=True, help='Data file (one value per line)')
    parser.add_argument('-a', '--alpha',   type=float, default=0.05, help='KS significance level (default: 0.05)')
    parser.add_argument('-b', '--bins',    type=int,   default=50,   help='Histogram bins (default: 50)')
    parser.add_argument('--distributions', nargs='+',
                        choices=DistributionFitter.DEFAULT_DISTRIBUTIONS,
                        metavar='DIST', help='Distributions to test')
    parser.add_argument('--no-plot',   action='store_true', help='Skip plots')
    parser.add_argument('--show-all',  action='store_true', help='Plot top-5 fits, not just the best')
    parser.add_argument('--no-floc0',  action='store_true',
                        help='Do NOT force loc=0 for non-negative distributions')
    parser.add_argument('--max-sample', type=int, default=2000, metavar='N',
                        help='Max observations used for fitting / KS test '
                             '(default: 2000). Use 0 to fit on the full dataset.')
    parser.add_argument('-o', '--output', help='Save results to file')
    parser.add_argument('--format', choices=['table', 'json', 'csv'], default='table',
                        help='Output format (default: table)')
    parser.add_argument('-v', '--verbose', action='store_true', help='Verbose logging')
    return parser


def save_results(fitter: DistributionFitter, filepath: str, fmt: str) -> None:
    """Save fitting results to table, CSV, or JSON."""
    import json, csv

    if fmt == 'table':
        with open(filepath, 'w', encoding='utf-8') as f:
            f.write(fitter.generate_summary_report())
            f.write("\n\nDetailed Results:\n" + "─" * 80 + "\n")
            for i, r in enumerate(fitter.results, 1):
                pnames = fitter.get_parameter_names(r.name)
                pairs  = ", ".join(f"{k}={v:.6g}" for k, v in zip(pnames, r.parameters))
                f.write(f"{i}. {r.name}\n")
                f.write(f"   scipy params : {pairs}\n")
                f.write(f"   KS / p-value : {r.statistic:.6f} / {r.p_value:.6f}\n")
                f.write(f"   Python code  : {fitter.get_python_random_code(r)}\n\n")

    elif fmt == 'csv':
        with open(filepath, 'w', newline='', encoding='utf-8') as f:
            w = csv.writer(f)
            w.writerow(['Distribution', 'KS_stat', 'p_value', 'SSE', 'Significant', 'Python_code'])
            for r in fitter.results:
                w.writerow([r.name, f"{r.statistic:.6f}", f"{r.p_value:.6f}",
                             f"{r.sse:.6f}", "Yes" if r.is_significant else "No",
                             fitter.get_python_random_code(r)])

    elif fmt == 'json':
        out = {
            'data_stats': {
                'n': len(fitter.data),
                'mean': float(fitter.data.mean()),
                'std':  float(fitter.data.std()),
                'min':  float(fitter.data.min()),
                'max':  float(fitter.data.max()),
            },
            'alpha': fitter.alpha,
            'results': []
        }
        for r in fitter.results:
            pnames = fitter.get_parameter_names(r.name)
            out['results'].append({
                'distribution': r.name,
                'ks_statistic': r.statistic,
                'p_value':      r.p_value,
                'sse':          r.sse,
                'significant':  r.is_significant,
                'scipy_params': dict(zip(pnames, [float(v) for v in r.parameters])),
                'python_code':  fitter.get_python_random_code(r),
            })
        with open(filepath, 'w', encoding='utf-8') as f:
            json.dump(out, f, indent=2, ensure_ascii=False)

    logger.info(f"Results saved → {filepath} ({fmt})")


def run_cli(args: argparse.Namespace) -> int:
    if args.verbose:
        logging.getLogger().setLevel(logging.DEBUG)

    try:
        data_path = resolve_data_path(args.data)
        force_loc_zero = not args.no_floc0

        fitter = DistributionFitter(alpha=args.alpha, bins=args.bins,
                                    force_loc_zero=force_loc_zero,
                                    max_sample_size=args.max_sample)
        fitter.load_data(data_path)

        print(f"\nData file : {data_path}")
        print(f"N={len(fitter.data):,}  mean={fitter.data.mean():.4f}  "
              f"std={fitter.data.std():.4f}  "
              f"min={fitter.data.min():.4f}  max={fitter.data.max():.4f}")
        if force_loc_zero:
            print("(Non-negative distributions fitted with floc=0)")

        dists = args.distributions or None
        results = fitter.fit_distributions(dists)

        if not results:
            logger.error("No distributions could be fitted.")
            return 1

        fitter.print_parameters()
        print(fitter.generate_summary_report())

        if args.output:
            save_results(fitter, args.output, args.format)

        if not args.no_plot:
            try:
                fitter.plot_results(show_all=args.show_all)
            except Exception as e:
                logger.warning(f"Plot failed: {e}")

        return 0

    except FileNotFoundError as e:
        logger.error(str(e)); return 1
    except ValueError as e:
        logger.error(str(e)); return 1
    except Exception as e:
        logger.error(f"Unexpected error: {e}")
        if args.verbose:
            import traceback; traceback.print_exc()
        return 1


def main():
    if len(sys.argv) > 1:
        parser = create_argument_parser()
        args   = parser.parse_args()
        sys.exit(run_cli(args))
    else:
        print("\nUsage : desk-distfit -d <data_file>")
        print("Example: desk-distfit -d input_data/arrivals.txt")
        print("Help   : desk-distfit -h")


if __name__ == "__main__":
    main()
