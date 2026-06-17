# ========================================================================================
# CHARTS 2h - REFACTORED FOR EFFECTIVE UTILIZATION
# ========================================================================================
import pandas as pd
import numpy as np
import plotly.express as px
import warnings
warnings.filterwarnings("ignore")

INPUT_FILE  = "cc_event_log.csv"
OUTPUT_HTML = "resource_2h_utilization.html"
BASE_DATETIME = pd.Timestamp("2025-01-01 03:00:00")
SIM_DURATION = 44_640

DEFAULT_CAPACITIES = {
    "Enfermeiro": 1, "Farmacia": 2, "Tec_Enfermagem": 6,
    "Eq_Assistencial_CTI": 1, "Eq_Medica": 5, "Anestesista": 5,
    "Tec_Radiologia": 2, "Eq_Radiologia": 2, "Func_CME": 1, "Eq_Higienizacao": 2
}

def get_effective_busy_time(tasks, slot_start_min, slot_end_min):
    """Calculates the duration of the union of intervals within a 2h slot."""
    # Clip tasks to the current slot window
    intervals = []
    for _, row in tasks.iterrows():
        start = max(row['timestamp_start'], slot_start_min)
        end = min(row['timestamp_complete'], slot_end_min)
        if start < end:
            intervals.append((start, end))
            
    if not intervals:
        return 0.0
    
    # Merge overlapping intervals
    intervals.sort()
    merged = []
    curr_start, curr_end = intervals[0]
    for next_start, next_end in intervals[1:]:
        if next_start < curr_end:
            curr_end = max(curr_end, next_end)
        else:
            merged.append((curr_start, curr_end))
            curr_start, curr_end = next_start, next_end
    merged.append((curr_start, curr_end))
    
    return sum(end - start for start, end in merged)

# 1. Load and Clean Data
df_raw = pd.read_csv(INPUT_FILE)
df_raw = df_raw.drop_duplicates(subset=["case_id", "activity", "lifecycle", "timestamp", "resource"])
df_raw["timestamp"] = pd.to_numeric(df_raw["timestamp"], errors="coerce")
df_raw = df_raw[df_raw["timestamp"] <= SIM_DURATION].copy()

# 2. Extract Durations
starts = df_raw[df_raw["lifecycle"] == "start"].copy()
completes = df_raw[df_raw["lifecycle"] == "complete"].copy()
durations = pd.merge(starts, completes, on=["case_id", "activity", "resource"], suffixes=("_start", "_complete"))
durations["resource_list"] = durations["resource"].str.split(r",\s*")
exploded = durations.explode("resource_list")

# 3. Compute Utilization per Slot
slot_labels = {i: f"{i:02d}:00–{i+2:02d}:00" for i in range(0, 24, 2)}
results = []

for res in DEFAULT_CAPACITIES.keys():
    res_tasks = exploded[exploded["resource_list"] == res].copy()
    for h in range(0, 24, 2):
        slot_start_m = h * 60
        slot_end_m = (h + 2) * 60
        
        # Filter tasks active in this 2h window
        active_in_slot = res_tasks[
            (res_tasks["timestamp_start"] < slot_end_m) & 
            (res_tasks["timestamp_complete"] > slot_start_m)
        ]
        
        busy_min = get_effective_busy_time(active_in_slot, slot_start_m, slot_end_m)
        # Assuming 1 unit of resource = 120 mins per 2h slot
        util = (busy_min / 120.0) * 100 
        
        results.append({"Resource": res, "Slot": slot_labels[h], "Util": util})

# 4. Plotting
df_res = pd.DataFrame(results)
matrix = df_res.pivot(index="Resource", columns="Slot", values="Util")

fig = px.imshow(
    matrix, color_continuous_scale="RdYlGn_r", zmin=0, zmax=100,
    labels=dict(x="Horário", y="Profissional", color="Ocupação (%)")
)
fig.update_layout(title="Taxa de Ocupação Efetiva (Capped at 100%)", height=700)
fig.write_html(OUTPUT_HTML)
print(f"Report saved to {OUTPUT_HTML}")