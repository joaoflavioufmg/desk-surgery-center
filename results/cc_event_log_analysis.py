"""
Discrete-Event Simulation Event Log Analysis
=============================================
Converts minute-based timestamps to datetime format and produces two
publication-quality charts:
  1. Histogram — patient arrival frequency in 2-hour intervals
  2. Line chart — average number of patients in the system per day
"""

import pandas as pd
import numpy as np
import matplotlib.pyplot as plt
import matplotlib.dates as mdates
import matplotlib.ticker as ticker
from matplotlib.gridspec import GridSpec
from matplotlib.patches import FancyBboxPatch
import matplotlib.patheffects as pe
import warnings
warnings.filterwarnings("ignore")

# ─────────────────────────────────────────────────────────────────────────────
# 0. CONFIGURATION
# ─────────────────────────────────────────────────────────────────────────────
INPUT_FILE      = "cc_event_log.csv"      # ← change path if needed
OUTPUT_FILE     = "cc_event_log_dashboard.png"
SIM_DURATION    = 50_000                  # total simulation minutes
BASE_DATETIME   = pd.Timestamp("2024-01-01 00:00:00")  # simulation epoch

PALETTE = {
    "bg":        "#0D1117",
    "panel":     "#161B22",
    "accent1":   "#00C6FF",   # cyan  – arrivals histogram
    "accent2":   "#FF6B6B",   # coral – census line
    "accent2b":  "#FF9999",   # lighter coral for fill
    "grid":      "#21262D",
    "text":      "#E6EDF3",
    "subtext":   "#8B949E",
    "white":     "#FFFFFF",
}

# ─────────────────────────────────────────────────────────────────────────────
# 1. LOAD RAW DATA
# ─────────────────────────────────────────────────────────────────────────────
print("Loading event log …")
df = pd.read_csv(INPUT_FILE)
print(f"  Rows loaded : {len(df):,}")
print(f"  Columns     : {df.columns.tolist()}")

# ─────────────────────────────────────────────────────────────────────────────
# 2. TIMESTAMP CONVERSION  (minutes → datetime)
# ─────────────────────────────────────────────────────────────────────────────
print("\nConverting minute-based timestamps to datetime …")

df["datetime"] = BASE_DATETIME + pd.to_timedelta(df["timestamp"], unit="m")

# Clip events that exceed the declared simulation horizon
df = df[df["timestamp"] <= SIM_DURATION].copy()
print(f"  Events within simulation horizon: {len(df):,}")
print(f"  Datetime range: {df['datetime'].min()} → {df['datetime'].max()}")

# ─────────────────────────────────────────────────────────────────────────────
# 3. EXTRACT PATIENT ARRIVALS
# ─────────────────────────────────────────────────────────────────────────────
print("\nExtracting patient arrivals …")

arrivals = (
    df[(df["activity"] == "Arrival") & (df["lifecycle"] == "complete")]
    [["case_id", "timestamp", "datetime"]]
    .rename(columns={"timestamp": "arrival_min", "datetime": "arrival_dt"})
    .reset_index(drop=True)
)
print(f"  Total arrivals : {len(arrivals):,}")

# 2-hour bins aligned to simulation start
bin_hours   = 2
bin_minutes = bin_hours * 60
bin_edges   = np.arange(0, SIM_DURATION + bin_minutes, bin_minutes)
bin_labels  = BASE_DATETIME + pd.to_timedelta(bin_edges, unit="m")

arrivals["bin_idx"] = np.digitize(arrivals["arrival_min"], bin_edges) - 1
arrival_counts = (
    arrivals
    .groupby("bin_idx")
    .size()
    .reindex(range(len(bin_edges) - 1), fill_value=0)
    .reset_index()
    .rename(columns={"index": "bin_idx", 0: "count"})
)
arrival_counts["bin_start_dt"] = BASE_DATETIME + pd.to_timedelta(
    arrival_counts["bin_idx"] * bin_minutes, unit="m"
)
print(f"  2-hour bins    : {len(arrival_counts)}")
print(f"  Max arrivals/2h: {arrival_counts['count'].max()}")

# ─────────────────────────────────────────────────────────────────────────────
# 4. COMPUTE DAILY AVERAGE CENSUS
# ─────────────────────────────────────────────────────────────────────────────
print("\nBuilding patient census timeline …")

# Get each patient's arrival and discharge times
discharges = (
    df[(df["activity"] == "Discharge") & (df["lifecycle"] == "complete")]
    [["case_id", "timestamp"]]
    .rename(columns={"timestamp": "discharge_min"})
)

patient_flow = arrivals[["case_id", "arrival_min"]].merge(
    discharges, on="case_id", how="left"
)
# Patients still in system at end of simulation
patient_flow["discharge_min"] = patient_flow["discharge_min"].fillna(SIM_DURATION)
print(f"  Patients tracked  : {len(patient_flow):,}")
print(f"  Without discharge : {patient_flow['discharge_min'].isna().sum()}")

# Evaluate census every 60 minutes (hourly snapshot)
sample_minutes = np.arange(0, SIM_DURATION + 60, 60)
arr_min = patient_flow["arrival_min"].values
dis_min = patient_flow["discharge_min"].values

census_per_hour = np.array([
    int(np.sum((arr_min <= t) & (dis_min > t)))
    for t in sample_minutes
])

sample_dt = BASE_DATETIME + pd.to_timedelta(sample_minutes, unit="m")

census_df = pd.DataFrame({"datetime": sample_dt, "census": census_per_hour})
census_df["day"] = census_df["datetime"].dt.floor("D")

daily_avg = (
    census_df
    .groupby("day")["census"]
    .mean()
    .reset_index()
    .rename(columns={"census": "avg_census"})
)
print(f"  Simulation days   : {len(daily_avg)}")
print(f"  Overall avg census: {daily_avg['avg_census'].mean():.2f} patients")

# ─────────────────────────────────────────────────────────────────────────────
# 5. VISUALISATION
# ─────────────────────────────────────────────────────────────────────────────
print("\nRendering dashboard …")

plt.rcParams.update({
    "font.family":      "monospace",
    "text.color":       PALETTE["text"],
    "axes.labelcolor":  PALETTE["text"],
    "xtick.color":      PALETTE["subtext"],
    "ytick.color":      PALETTE["subtext"],
    "axes.edgecolor":   PALETTE["grid"],
    "figure.facecolor": PALETTE["bg"],
    "axes.facecolor":   PALETTE["panel"],
    "axes.grid":        True,
    "grid.color":       PALETTE["grid"],
    "grid.linewidth":   0.7,
    "grid.alpha":       1.0,
})

fig = plt.figure(figsize=(20, 13), dpi=140)
fig.patch.set_facecolor(PALETTE["bg"])

gs = GridSpec(
    2, 1,
    figure=fig,
    top=0.88, bottom=0.08,
    left=0.06, right=0.97,
    hspace=0.52,
)

# ── TITLE BLOCK ─────────────────────────────────────────────────────────────
fig.text(
    0.5, 0.955,
    "SURGICAL CENTER  ·  DISCRETE-EVENT SIMULATION ANALYSIS",
    ha="center", va="center",
    fontsize=16, fontweight="bold",
    color=PALETTE["white"], fontfamily="monospace",
)
fig.text(
    0.5, 0.927,
    f"Simulation horizon: {SIM_DURATION:,} min  ·  "
    f"Epoch: {BASE_DATETIME.strftime('%Y-%m-%d %H:%M')}  ·  "
    f"Patients: {len(arrivals):,}  ·  "
    f"Events: {len(df):,}",
    ha="center", va="center",
    fontsize=9, color=PALETTE["subtext"], fontfamily="monospace",
)

# thin separator line
fig.add_artist(
    plt.Line2D([0.06, 0.97], [0.91, 0.91],
               transform=fig.transFigure,
               color=PALETTE["accent1"], linewidth=0.8, alpha=0.5)
)

# ── CHART 1: ARRIVAL HISTOGRAM ───────────────────────────────────────────────
ax1 = fig.add_subplot(gs[0])

x = arrival_counts["bin_start_dt"]
y = arrival_counts["count"]

bar_width_days = bin_minutes / (60 * 24) * 0.88   # bar width in date-unit days

bars = ax1.bar(
    x, y,
    width=bar_width_days,
    color=PALETTE["accent1"],
    alpha=0.85,
    edgecolor="none",
    zorder=3,
    align="edge",
)

# subtle gradient shimmer: top portion brighter
for bar in bars:
    bx, by = bar.get_x(), bar.get_y()
    bw, bh = bar.get_width(), bar.get_height()
    if bh > 0:
        ax1.add_patch(FancyBboxPatch(
            (bx, by + bh * 0.75), bw, bh * 0.25,
            boxstyle="square,pad=0",
            linewidth=0, color="white", alpha=0.12, zorder=4,
        ))

# rolling 24-hour average overlay
window = 12  # 12 × 2h bins = 24 h
rolling_avg = arrival_counts["count"].rolling(window, center=True, min_periods=1).mean()
ax1.plot(
    x + pd.Timedelta(minutes=bin_minutes / 2),
    rolling_avg,
    color="white", linewidth=1.4, alpha=0.6,
    linestyle="--", zorder=5, label="24-h rolling avg",
)

# annotation: peak bin
peak_idx = arrival_counts["count"].idxmax()
peak_x   = arrival_counts.loc[peak_idx, "bin_start_dt"]
peak_y   = arrival_counts.loc[peak_idx, "count"]
ax1.annotate(
    f" Peak: {int(peak_y)} arrivals\n {peak_x.strftime('%Y-%m-%d %H:%M')}",
    xy=(peak_x + pd.Timedelta(minutes=bin_minutes / 2), peak_y),
    xytext=(peak_x + pd.Timedelta(hours=48), peak_y + 0.5),
    color=PALETTE["white"],
    fontsize=8, fontfamily="monospace",
    arrowprops=dict(arrowstyle="->", color=PALETTE["accent1"], lw=1.2),
    zorder=6,
)

# axes formatting
ax1.set_title(
    "PATIENT ARRIVALS — FREQUENCY DISTRIBUTION  (2-hour intervals)",
    loc="left", pad=10, fontsize=10, fontweight="bold",
    color=PALETTE["text"], fontfamily="monospace",
)
ax1.set_ylabel("Arrivals per 2-h interval", fontsize=9, labelpad=8)
ax1.set_xlabel("Simulation datetime", fontsize=9, labelpad=8)
ax1.xaxis.set_major_formatter(mdates.DateFormatter("%b %d\n%H:%M"))
ax1.xaxis.set_major_locator(mdates.DayLocator(interval=3))
ax1.yaxis.set_major_locator(ticker.MaxNLocator(integer=True))
ax1.set_xlim(bin_labels[0], bin_labels[-1])
ax1.set_ylim(0, peak_y * 1.25)
ax1.tick_params(axis="both", labelsize=8)

leg1 = ax1.legend(
    fontsize=8, loc="upper left",
    facecolor=PALETTE["bg"], edgecolor=PALETTE["grid"],
    labelcolor=PALETTE["subtext"],
)

# stat box top-right
total_arr = len(arrivals)
avg_arr_day = total_arr / (SIM_DURATION / (24 * 60))
stats_text = (
    f"  Total  : {total_arr:>5,} patients\n"
    f"  Avg/day: {avg_arr_day:>6.1f}\n"
    f"  Bin    :  2 h"
)
ax1.text(
    0.995, 0.97, stats_text,
    transform=ax1.transAxes,
    ha="right", va="top", fontsize=7.5, fontfamily="monospace",
    color=PALETTE["subtext"],
    bbox=dict(boxstyle="round,pad=0.5", facecolor=PALETTE["bg"],
              edgecolor=PALETTE["grid"], alpha=0.85),
)

ax1.spines["top"].set_visible(False)
ax1.spines["right"].set_visible(False)

# ── CHART 2: DAILY AVERAGE CENSUS ───────────────────────────────────────────
ax2 = fig.add_subplot(gs[1])

x2 = daily_avg["day"]
y2 = daily_avg["avg_census"]

# shaded area under line
ax2.fill_between(
    x2, y2,
    alpha=0.18, color=PALETTE["accent2"], zorder=2,
)
ax2.fill_between(
    x2, y2,
    alpha=0.06, color=PALETTE["accent2"], zorder=2,
)

# main line
ax2.plot(
    x2, y2,
    color=PALETTE["accent2"], linewidth=2.2,
    zorder=4, solid_capstyle="round",
)

# dots at each day
ax2.scatter(
    x2, y2,
    s=42, color=PALETTE["accent2"], edgecolors=PALETTE["bg"],
    linewidths=1.2, zorder=5,
)

# overall mean reference line
overall_mean = y2.mean()
ax2.axhline(
    overall_mean,
    color="white", linewidth=1.0, linestyle=":", alpha=0.45,
    zorder=3, label=f"Overall mean: {overall_mean:.2f} patients",
)

# annotate max day
max_day_idx = y2.idxmax()
max_day_x   = daily_avg.loc[max_day_idx, "day"]
max_day_y   = daily_avg.loc[max_day_idx, "avg_census"]
ax2.annotate(
    f" Day max: {max_day_y:.1f}\n {max_day_x.strftime('%Y-%m-%d')}",
    xy=(max_day_x, max_day_y),
    xytext=(max_day_x + pd.Timedelta(days=1.5), max_day_y + 0.4),
    color=PALETTE["white"],
    fontsize=8, fontfamily="monospace",
    arrowprops=dict(arrowstyle="->", color=PALETTE["accent2"], lw=1.2),
    zorder=6,
)

# axes formatting
ax2.set_title(
    "AVERAGE PATIENTS IN SYSTEM — DAILY PROFILE",
    loc="left", pad=10, fontsize=10, fontweight="bold",
    color=PALETTE["text"], fontfamily="monospace",
)
ax2.set_ylabel("Avg patients in system", fontsize=9, labelpad=8)
ax2.set_xlabel("Simulation date", fontsize=9, labelpad=8)
ax2.xaxis.set_major_formatter(mdates.DateFormatter("%b %d"))
ax2.xaxis.set_major_locator(mdates.DayLocator(interval=2))
ax2.yaxis.set_major_locator(ticker.MaxNLocator(nbins=6, integer=False))
ax2.set_xlim(x2.min() - pd.Timedelta(hours=12), x2.max() + pd.Timedelta(hours=12))
ax2.set_ylim(0, max_day_y * 1.25)
ax2.tick_params(axis="both", labelsize=8)

leg2 = ax2.legend(
    fontsize=8, loc="upper left",
    facecolor=PALETTE["bg"], edgecolor=PALETTE["grid"],
    labelcolor=PALETTE["subtext"],
)

# stat box
min_census = y2.min()
max_census = y2.max()
stats_text2 = (
    f"  Min avg : {min_census:>5.2f}\n"
    f"  Mean avg: {overall_mean:>5.2f}\n"
    f"  Max avg : {max_census:>5.2f}"
)
ax2.text(
    0.995, 0.97, stats_text2,
    transform=ax2.transAxes,
    ha="right", va="top", fontsize=7.5, fontfamily="monospace",
    color=PALETTE["subtext"],
    bbox=dict(boxstyle="round,pad=0.5", facecolor=PALETTE["bg"],
              edgecolor=PALETTE["grid"], alpha=0.85),
)

ax2.spines["top"].set_visible(False)
ax2.spines["right"].set_visible(False)

# ─────────────────────────────────────────────────────────────────────────────
# 6. EXPORT
# ─────────────────────────────────────────────────────────────────────────────
plt.savefig(OUTPUT_FILE, dpi=180, bbox_inches="tight", facecolor=PALETTE["bg"])
print(f"\n✓ Dashboard saved → {OUTPUT_FILE}")
plt.show()
