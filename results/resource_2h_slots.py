"""
Resource 2-Hour Time Slot Utilization Heatmap (Cleaned Base)
===========================================================
Mapeia a ocupação real em janelas de 2h excluindo os dados de pacientes cancelados.
"""

import pandas as pd
import numpy as np
import plotly.express as px
import warnings
warnings.filterwarnings("ignore")

INPUT_FILE  = "cc_event_log.csv"
OUTPUT_HTML = "resource_2h_utilization.html"
BASE_DATETIME = pd.Timestamp("2025-01-01 03:00:00")
SIM_DURATION = 50_000

DEFAULT_CAPACITIES = {
    "Enfermeiro": 3, "Farmacia": 2, "Tec_Enfermagem": 11, "Eq_Assistencial_CTI": 1,
    "Eq_Medica": 6, "Anestesista": 6, "Tec_Radiologia": 2, "Eq_Radiologia": 4,
    "Func_CME": 2, "Eq_Higienizacao": 2
}

RESOURCE_SCHEDULE = {
    "Eq_Medica": [
        (0, 2, 4), (2, 4, 4), (4, 6, 6), (6, 8, 6), (8, 10, 6), (10, 12, 6),
        (12, 14, 6), (14, 16, 6), (16, 18, 6), (18, 20, 4), (20, 22, 4), (22, 24, 4)
    ],
    "Enfermeiro": [(0, 6, 1), (6, 18, 2), (18, 24, 2)],
    "Tec_Enfermagem": [(0, 6, 10), (6, 18, 11), (18, 24, 11)]
}

print("Carregando dados para análise do Heatmap de 2 horas...")
df_raw = pd.read_csv(INPUT_FILE)
df_raw["timestamp"] = pd.to_numeric(df_raw["timestamp"], errors="coerce")
df_raw = df_raw[df_raw["timestamp"] <= SIM_DURATION].copy()
df_raw["data_formatada"] = BASE_DATETIME + pd.to_timedelta(df_raw["timestamp"], unit="m")

# Identificação e Exclusão de Cancelados
cancelled_cases = set(df_raw[df_raw["activity"] == "CC_busy_Pac_Sai_CC"]["case_id"].unique())
df = df_raw[~df_raw["case_id"].isin(cancelled_cases)].copy()

# 1. Mapeamento de tempo de relógio
timeline_hours = (BASE_DATETIME + pd.to_timedelta(np.arange(0, int(SIM_DURATION)), unit="m")).hour
hours_distribution = pd.Series(timeline_hours).value_counts().to_dict()

slot_labels = {i: f"{i:02d}:00–{i+2:02d}:00" for i in range(0, 24, 2)}
ordered_slots = [slot_labels[i] for i in range(0, 24, 2)]

resource_slot_capacities = {}
for res in DEFAULT_CAPACITIES:
    resource_slot_capacities[res] = {}
    default_cap = DEFAULT_CAPACITIES[res]
    hourly_staff = {h: default_cap for h in range(24)}
    if res in RESOURCE_SCHEDULE:
        for (start_h, end_h, cap) in RESOURCE_SCHEDULE[res]:
            for h in range(start_h, end_h): hourly_staff[h] = cap
                
    for slot_start in range(0, 24, 2):
        lbl = slot_labels[slot_start]
        minutos_h1 = hours_distribution.get(slot_start, 0) * hourly_staff[slot_start]
        minutos_h2 = hours_distribution.get(slot_start + 1, 0) * hourly_staff[slot_start + 1]
        resource_slot_capacities[res][lbl] = float(minutos_h1 + minutos_h2)

# 2. Processamento das Durações Ativas
starts = df[df["lifecycle"] == "start"].copy()
completes = df[df["lifecycle"] == "complete"].copy()
durations = pd.merge(starts, completes, on=["case_id", "activity", "resource"], suffixes=("_start", "_complete"))
durations["duration_min"] = durations["timestamp_complete"] - durations["timestamp_start"]

# CORREÇÃO AQUI: Remove apenas se a coluna de recurso for nula, preservando dados parciais das decisões
durations = durations.dropna(subset=["resource"])

durations["resource_list"] = durations["resource"].str.split(r",\s*")
exploded_durations = durations.explode("resource_list")
exploded_durations = exploded_durations.rename(columns={"resource_list": "individual_resource"})
exploded_durations = exploded_durations[exploded_durations["individual_resource"].isin(DEFAULT_CAPACITIES.keys())]

exploded_durations["Start_Hour"] = exploded_durations["data_formatada_start"].dt.hour
exploded_durations["Time_Slot"] = (exploded_durations["Start_Hour"] // 2) * 2
exploded_durations["Intervalo Horário"] = exploded_durations["Time_Slot"].map(slot_labels)

matrix_sums = exploded_durations.groupby(["individual_resource", "Intervalo Horário"])["duration_min"].sum().unstack(fill_value=0.0)
matrix_sums = matrix_sums.reindex(columns=ordered_slots, fill_value=0.0)

matrix_utilization = pd.DataFrame(index=matrix_sums.index, columns=matrix_sums.columns)
for res in matrix_sums.index:
    for col in matrix_sums.columns:
        total_trabalhado = matrix_sums.loc[res, col]
        max_disponivel = resource_slot_capacities[res][col]
        matrix_utilization.loc[res, col] = (total_trabalhado / max_disponivel) * 100 if max_disponivel > 0 else 0.0

matrix_utilization = matrix_utilization.fillna(0.0).astype(float)
matrix_utilization = matrix_utilization.loc[matrix_sums.sum(axis=1).sort_values().index]

print("Gerando mapa de calor...")
fig = px.imshow(
    matrix_utilization,
    labels=dict(x="Intervalo do Dia (Janelas de 2h)", y="Profissional (Individual)", color="Ocupação Ajustada (%)"),
    x=matrix_utilization.columns, y=matrix_utilization.index,
    color_continuous_scale="Viridis", zmin=0, zmax=100, aspect="auto"
)
fig.update_traces(hovertemplate="Profissional: %{y}<br>Horário: %{x}<br>Ocupação Real: %{z:.1f}%<extra></extra>")
fig.update_layout(
    title=dict(
        text="<b>TAXA DE OCUPAÇÃO REAL (BASE LIMPA DE CANCELAMENTOS)</b><br><span style='font-size:12px; color:#8B949E'>Métrica calibrada apenas para o efetivo cirúrgico executado</span>",
        font=dict(color="#E6EDF3", family="monospace")
    ),
    paper_bgcolor="#0D1117", plot_bgcolor="#161B22", font=dict(color="#E6EDF3", family="monospace"),
    xaxis_tickangle=-45, height=750, width=1100
)

fig.write_html(OUTPUT_HTML)
print(f"✓ Gráfico de slots de 2h salvo com sucesso → {OUTPUT_HTML}")