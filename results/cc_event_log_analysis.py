"""
Discrete-Event Simulation Event Log Analysis (Interactive HTML Version)
======================================================================
1. Converte timestamps baseados em minutos da simulação para Datetimes reais.
2. Identifica e remove pacientes cancelados com tempo de permanência zero (CC_busy_Pac_Sai_CC).
3. Adiciona métricas diárias acumuladas de Cirurgias Concluídas vs. Canceladas no gráfico do Censo.
4. CORREÇÃO SOLICITADA: Adiciona subtítulo dinâmico no Gráfico 2 com as médias diárias.
5. Produz gráficos HTML interativos via Plotly reunidos em um único Dashboard.
"""

import pandas as pd
import numpy as np
import plotly.graph_objects as go
from plotly.subplots import make_subplots
import warnings
warnings.filterwarnings("ignore")

# ─────────────────────────────────────────────────────────────────────────────
# 0. CONFIGURAÇÃO, ESCALA E CONSTANTES
# ─────────────────────────────────────────────────────────────────────────────
INPUT_FILE      = "cc_event_log.csv"      
OUTPUT_HTML     = "cc_event_log_dashboard.html"
SIM_DURATION    = 50_000                  
BASE_DATETIME   = pd.Timestamp("2025-01-01 03:00:00")  

# Capacidades Padrão (Default)
DEFAULT_CAPACITIES = {
    "Enfermeiro": 3, "Farmacia": 2, "Tec_Enfermagem": 11, "Eq_Assistencial_CTI": 1,
    "Eq_Medica": 6, "Anestesista": 6, "Tec_Radiologia": 2, "Eq_Radiologia": 4,
    "Func_CME": 2, "Eq_Higienizacao": 2
}

# Escala de dimensionamento dinâmico por hora do dia
RESOURCE_SCHEDULE = {
    "Eq_Medica": [
        (0, 2, 4), (2, 4, 4), (4, 6, 6), (6, 8, 6), (8, 10, 6), (10, 12, 6),
        (12, 14, 6), (14, 16, 6), (16, 18, 6), (18, 20, 4), (20, 22, 4), (22, 24, 4)
    ],
    "Enfermeiro": [(0, 6, 1), (6, 18, 2), (18, 24, 2)],
    "Tec_Enfermagem": [(0, 6, 10), (6, 18, 11), (18, 24, 11)]
}

COLORS = {
    "bg":        "#0D1117",
    "panel":     "#161B22",
    "accent1":   "#00C6FF",   # Ciano (Chegadas)
    "accent2":   "#FF6B6B",   # Coral (Censo)
    "completed": "#2EA043",   # Verde (Concluídas)
    "cancelled": "#A371F7",   # Roxo (Canceladas)
    "grid":      "#21262D",
    "text":      "#E6EDF3",
    "subtext":   "#8B949E",
    "morning":   "#FFD166",   # Manhã
    "afternoon": "#F77F00",   # Tarde
    "night":     "#118AB2",   # Noite
}

# ─────────────────────────────────────────────────────────────────────────────
# 1. CARGA DE DADOS E SEPARAÇÃO DE CIRURGIAS CANCELADAS
# ─────────────────────────────────────────────────────────────────────────────
print("Carregando e tratando log de eventos...")
df_raw = pd.read_csv(INPUT_FILE)
df_raw["timestamp"] = pd.to_numeric(df_raw["timestamp"], errors="coerce")
df_raw = df_raw[df_raw["timestamp"] <= SIM_DURATION].copy()

# Datetime real absoluto baseado nos minutos da simulação
df_raw["data_formatada"] = BASE_DATETIME + pd.to_timedelta(df_raw["timestamp"], unit="m")

# Identificação de pacientes cancelados
cancelled_cases = set(df_raw[df_raw["activity"] == "CC_busy_Pac_Sai_CC"]["case_id"].unique())

# Filtra a base principal removendo cancelados
df = df_raw[~df_raw["case_id"].isin(cancelled_cases)].copy()

# Ajuste do Horário e Turno
df["Hora_Dia"] = df["data_formatada"].dt.hour + (df["data_formatada"].dt.minute / 60.0)

def assign_shift(dt):
    hour = dt.hour
    if 7 <= hour < 13: return "Manhã"
    elif 13 <= hour < 19: return "Tarde"
    else: return "Noite"

df["Turno"] = df["data_formatada"].apply(assign_shift)

# ─────────────────────────────────────────────────────────────────────────────
# 2. MODELAGEM DA CAPACIDADE MINUTO A MINUTO (STAFFING DINÂMICO)
# ─────────────────────────────────────────────────────────────────────────────
print("Calculando capacidade dinâmica de cada recurso minuto a minuto...")
timeline_minutes = BASE_DATETIME + pd.to_timedelta(np.arange(0, int(SIM_DURATION)), unit="m")
timeline_hours = timeline_minutes.hour
timeline_shifts = timeline_minutes.map(assign_shift)

resource_capacity_totals = {res: {"Manhã": 0.0, "Tarde": 0.0, "Noite": 0.0} for res in DEFAULT_CAPACITIES}

for res in DEFAULT_CAPACITIES:
    default_cap = DEFAULT_CAPACITIES[res]
    if res in RESOURCE_SCHEDULE:
        hourly_map = {}
        for (start_h, end_h, cap) in RESOURCE_SCHEDULE[res]:
            for h in range(start_h, end_h): hourly_map[h] = cap
        minute_capacities = np.array([hourly_map.get(h, default_cap) for h in timeline_hours])
    else:
        minute_capacities = np.full(int(SIM_DURATION), default_cap)
    
    for shift in ["Manhã", "Tarde", "Noite"]:
        mask = (timeline_shifts == shift)
        resource_capacity_totals[res][shift] = float(np.sum(minute_capacities[mask]))

# ─────────────────────────────────────────────────────────────────────────────
# 3. MÉTRICA 1: HISTOGRAMA DE CHEGADAS (INTERVALOS DE 2H)
# ─────────────────────────────────────────────────────────────────────────────
arrivals = df[(df["activity"] == "Arrival") & (df["lifecycle"] == "complete")].copy()
bin_minutes = 120
bin_edges = np.arange(0, SIM_DURATION + bin_minutes, bin_minutes)

arrivals["bin_idx"] = np.digitize(arrivals["timestamp"], bin_edges) - 1
arrival_counts = arrivals.groupby("bin_idx").size().reindex(range(len(bin_edges) - 1), fill_value=0).reset_index(name="count")
arrival_counts["bin_start_dt"] = BASE_DATETIME + pd.to_timedelta(arrival_counts["bin_idx"] * bin_minutes, unit="m")

# ─────────────────────────────────────────────────────────────────────────────
# 4. MÉTRICA 2: CENSO MÉDIO + CALCULOS DIÁRIOS DE DESEMPENHO CIRÚRGICO
# ─────────────────────────────────────────────────────────────────────────────
print("Processando histórico diário do Censo, Conclusões e Cancelamentos...")

# 4.1 Censo de pacientes ativos por hora
discharges = df[(df["activity"] == "Discharge") & (df["lifecycle"] == "complete")][["case_id", "timestamp"]].rename(columns={"timestamp": "discharge_min"})
patient_flow = arrivals[["case_id", "timestamp"]].rename(columns={"timestamp": "arrival_min"}).merge(discharges, on="case_id", how="left")
patient_flow["discharge_min"] = patient_flow["discharge_min"].fillna(SIM_DURATION)

sample_minutes = np.arange(0, SIM_DURATION + 60, 60)
arr_min, dis_min = patient_flow["arrival_min"].values, patient_flow["discharge_min"].values
census_per_hour = np.array([int(np.sum((arr_min <= t) & (dis_min > t))) for t in sample_minutes])

census_df = pd.DataFrame({"datetime": BASE_DATETIME + pd.to_timedelta(sample_minutes, unit="m"), "census": census_per_hour})
census_df["day"] = census_df["datetime"].dt.floor("D")
daily_avg = census_df.groupby("day")["census"].mean().reset_index(name="avg_census")

# 4.2 Total diário de Cirurgias Concluídas
completed_events = df[(df["activity"] == "Discharge") & (df["lifecycle"] == "complete")].copy()
completed_events["day"] = completed_events["data_formatada"].dt.floor("D")
daily_completed = completed_events.groupby("day").size().reindex(daily_avg["day"], fill_value=0).reset_index(name="total_completed")

# 4.3 Total diário de Cirurgias Canceladas
cancelled_events = df_raw[df_raw["case_id"].isin(cancelled_cases) & (df_raw["activity"] == "Discharge") & (df_raw["lifecycle"] == "complete")].copy()
cancelled_events["day"] = cancelled_events["data_formatada"].dt.floor("D")
daily_cancelled = cancelled_events.groupby("day").size().reindex(daily_avg["day"], fill_value=0).reset_index(name="total_cancelled")

# Fusão dos dados do painel 2
metrics_day = daily_avg.merge(daily_completed, on="day").merge(daily_cancelled, on="day")

# CÁLCULO DAS MÉDIAS GERAIS DIÁRIAS PARA O SUBTÍTULO
mean_completed_day = metrics_day["total_completed"].mean()
mean_cancelled_day = metrics_day["total_cancelled"].mean()

# ─────────────────────────────────────────────────────────────────────────────
# 5. MÉTRICA 3: TAXA DE OCUPAÇÃO REAL POR RECURSO INDIVIDUAL CONSOLIDADO
# ─────────────────────────────────────────────────────────────────────────────
print("Calculando a taxa de ocupação real dos recursos...")
starts = df[df["lifecycle"] == "start"].copy()
completes = df[df["lifecycle"] == "complete"].copy()

activity_durations = pd.merge(starts, completes, on=["case_id", "activity", "resource"], suffixes=("_start", "_complete"))
activity_durations["duration_min"] = activity_durations["timestamp_complete"] - activity_durations["timestamp_start"]
activity_durations = activity_durations.dropna(subset=["resource"])
activity_durations = activity_durations[activity_durations["resource"].str.strip() != ""]

# Desmembramento de recursos complexos
activity_durations["resource_list"] = activity_durations["resource"].str.split(r",\s*")
exploded_durations = activity_durations.explode("resource_list")
exploded_durations = exploded_durations.rename(columns={"resource_list": "individual_resource"})
exploded_durations = exploded_durations[exploded_durations["individual_resource"].isin(DEFAULT_CAPACITIES.keys())]

resource_shift_sums = exploded_durations.groupby(["individual_resource", "Turno_start"])["duration_min"].sum().unstack(fill_value=0.0)

for shift in ["Manhã", "Tarde", "Noite"]:
    if shift not in resource_shift_sums.columns: resource_shift_sums[shift] = 0.0
resource_shift_sums = resource_shift_sums[["Manhã", "Tarde", "Noite"]]

resource_utilization_pct = pd.DataFrame(index=resource_shift_sums.index, columns=["Manhã", "Tarde", "Noite"])
for res in resource_shift_sums.index:
    for shift in ["Manhã", "Tarde", "Noite"]:
        total_trabalhado = resource_shift_sums.loc[res, shift]
        capacidade_turno = resource_capacity_totals[res][shift]
        resource_utilization_pct.loc[res, shift] = (total_trabalhado / capacidade_turno) * 100 if capacidade_turno > 0 else 0.0

resource_utilization_pct = resource_utilization_pct.fillna(0.0)
resource_utilization_pct = resource_utilization_pct.loc[resource_utilization_pct.sum(axis=1).sort_values().index]

# ─────────────────────────────────────────────────────────────────────────────
# 6. CONSTRUÇÃO DO DASHBOARD INTERATIVO
# ─────────────────────────────────────────────────────────────────────────────
print("Renderizando dashboard interativo unificado...")

# Montagem das strings de títulos com as quebras de linha e subtextos configurados
sub_chart_2 = f"<b>PERFIL DIÁRIO: CENSO MÉDIO E DESEMPENHO CIRÚRGICO ACUMULADO</b><br><span style='font-size:12px; color:{COLORS['subtext']}'>Horizonte: {SIM_DURATION:,} min | Média de Cirurgias Concluídas / Dia: {mean_completed_day:.2f} | Média de Cirurgias Canceladas / Dia: {mean_cancelled_day:.2f}</span>"

fig = make_subplots(
    rows=3, cols=1,
    subplot_titles=(
        "<b>DISTRIBUIÇÃO DE CHEGADAS DE PACIENTES REAIS (Intervalos de 2h)</b>",
        sub_chart_2,  # Subtítulo customizado aplicado exclusivamente aqui
        "<b>TAXA DE OCUPAÇÃO REAL AJUSTADA POR RECURSO (% da Capacidade do Turno)</b>"
    ),
    vertical_spacing=0.08
)

# Gráfico 1: Chegadas
fig.add_trace(go.Bar(x=arrival_counts["bin_start_dt"], y=arrival_counts["count"], name="Chegadas (Reais)", marker_color=COLORS["accent1"], opacity=0.85), row=1, col=1)

# Gráfico 2: Linhas Temporais
fig.add_trace(go.Scatter(x=metrics_day["day"], y=metrics_day["avg_census"], mode='lines+markers', name="Censo Médio", line=dict(color=COLORS["accent2"], width=3), marker=dict(size=6)), row=2, col=1)
fig.add_trace(go.Scatter(x=metrics_day["day"], y=metrics_day["total_completed"], mode='lines+markers', name="Cirurgias Concluídas / Dia", line=dict(color=COLORS["completed"], width=2.5, dash="dash"), marker=dict(size=6)), row=2, col=1)
fig.add_trace(go.Scatter(x=metrics_day["day"], y=metrics_day["total_cancelled"], mode='lines+markers', name="Cirurgias Canceladas / Dia", line=dict(color=COLORS["cancelled"], width=2.5, dash="dot"), marker=dict(size=6)), row=2, col=1)

# Gráfico 3: Utilização Agrupada
for shift, color in zip(["Manhã", "Tarde", "Noite"], [COLORS["morning"], COLORS["afternoon"], COLORS["night"]]):
    fig.add_trace(
        go.Bar(
            y=resource_utilization_pct.index, x=resource_utilization_pct[shift], 
            name=shift, orientation='h', marker_color=color,
            hovertemplate=f"Profissional: %{{y}}<br>Turno: {shift}<br>Ocupação Real: %{{x:.1f}}%"
        ),
        row=3, col=1
    )

fig.update_layout(
    title=dict(
        text=f"<b>CENTRO CIRÚRGICO · PERFORMANCE E CONSUMO DE CAPACIDADE</b><br><span style='font-size:12px; color:{COLORS['subtext']}'>Análise de logs de simulação em tempo real</span>",
        font=dict(size=18, color=COLORS["text"], family="monospace")
    ),
    paper_bgcolor=COLORS["bg"],
    plot_bgcolor=COLORS["panel"],
    font=dict(color=COLORS["text"], family="monospace"),
    barmode='group',
    height=1600,
    showlegend=True
)

fig.update_xaxes(showgrid=True, gridcolor=COLORS["grid"], zeroline=False)
fig.update_yaxes(showgrid=True, gridcolor=COLORS["grid"], zeroline=False)
fig.update_xaxes(title_text="Quantidade Diária / Censo de Pacientes", row=2, col=1)
fig.update_xaxes(title_text="Taxa de Ocupação Real (%)", row=3, col=1)

fig.write_html(OUTPUT_HTML)
print(f"✓ Dashboard interativo gerado com subtítulo atualizado no Censo → {OUTPUT_HTML}")