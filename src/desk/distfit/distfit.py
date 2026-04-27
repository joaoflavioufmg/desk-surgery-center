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

    def __init__(self, alpha: float = 0.05, bins: int = 50, force_loc_zero: bool = True):
        """
        Args:
            alpha:          Significance level for KS test.
            bins:           Histogram bins for SSE calculation and plots.
            force_loc_zero: If True (default), fit non-negative distributions
                            with floc=0. This produces cleaner Python code
                            and avoids the spurious loc ≠ 0 issue that caused
                            the original lognorm/weibull translation bugs.
        """
        self.alpha = alpha
        self.bins = bins
        self.force_loc_zero = force_loc_zero
        self.results: List[DistributionResult] = []
        self.data: Optional[pd.Series] = None

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
        data_min = self.data.min()
        use_floc0 = (
            self.force_loc_zero
            and dist_name in self._NONNEG_DISTRIBUTIONS
            and data_min >= 0
        )
        with warnings.catch_warnings():
            warnings.filterwarnings('ignore')
            if use_floc0:
                return dist.fit(self.data, floc=0)
            return dist.fit(self.data)

    def fit_distributions(self, distributions: Optional[List[str]] = None) -> List[DistributionResult]:
        """
        Fit all requested distributions, run KS test, compute SSE.
        Results are sorted by p-value (descending).
        """
        if self.data is None:
            raise ValueError("No data loaded. Call load_data() or set_data() first.")

        distributions = distributions or self.DEFAULT_DISTRIBUTIONS
        self.results = []

        y_hist, x_edges = np.histogram(self.data, bins=self.bins, density=True)
        x_mid = (x_edges[:-1] + x_edges[1:]) / 2.0

        print(f"\n{'#':<4} {'Distribution':<15} {'KS stat':<10} {'p-value':<10} {'SSE':<12} {'Pass α'}")
        print("─" * 62)

        for i, dist_name in enumerate(distributions):
            try:
                dist = getattr(st, dist_name)
                params = self._fit_single(dist_name, dist)

                ks_stat, p_value = st.kstest(self.data, dist_name, params)

                arg = params[:-2] if len(params) > 2 else []
                loc, scale = params[-2], params[-1]
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

    def plot_results(self, show_all: bool = False, figsize: Tuple = (13, 5)) -> None:
        if not self.results or self.data is None:
            logger.warning("Nothing to plot.")
            return

        best = self.get_best_fit()
        results_to_plot = self.results[:5] if show_all else [best]

        fig, (ax1, ax2) = plt.subplots(1, 2, figsize=figsize)

        # Left: histogram only
        self.data.hist(bins=self.bins, density=True, alpha=0.7, ax=ax1,
                       color='steelblue', edgecolor='white', linewidth=0.4)
        ax1.set_title("Data Histogram", fontweight='bold')
        ax1.set_xlabel("Value")
        ax1.set_ylabel("Density")
        ax1.grid(True, alpha=0.3)

        # Right: histogram + fitted PDFs
        self.data.hist(bins=self.bins, density=True, alpha=0.4, ax=ax2,
                       color='lightgray', edgecolor='white', linewidth=0.4, label='Data')

        x_min, x_max = self.data.min(), self.data.max()
        pad = 0.1 * (x_max - x_min)
        x = np.linspace(max(0, x_min - pad), x_max + pad, 1000)

        colors = plt.cm.tab10.colors
        for idx, r in enumerate(results_to_plot):
            try:
                dist = getattr(st, r.name)
                arg  = r.parameters[:-2] if len(r.parameters) > 2 else []
                loc, scale = r.parameters[-2], r.parameters[-1]
                y = dist.pdf(x, *arg, loc=loc, scale=scale)
                label = f"{r.name}  p={r.p_value:.3f}"
                ax2.plot(x, y, lw=2, color=colors[idx % 10], label=label)
            except Exception as e:
                logger.warning(f"Plot error for {r.name}: {e}")

        python_code = self.get_python_random_code(best)
        ax2.set_title(f"Fit Comparison\n{python_code}", fontsize=9, fontweight='bold')
        ax2.set_xlabel("Value")
        ax2.set_ylabel("Density")
        ax2.legend(fontsize=8)
        ax2.grid(True, alpha=0.3)

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
                                    force_loc_zero=force_loc_zero)
        fitter.load_data(data_path)

        print(f"\nData file : {data_path}")
        print(f"N={len(fitter.data)}  mean={fitter.data.mean():.4f}  "
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
