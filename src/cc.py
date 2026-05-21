# =====================================================================
# FILE: hrtn.py
# =====================================================================
import random
import math
import sys
import simpy                          # ← required for the Sala_CC capacity gate
from desk.stats.factorial import FactorialExperiment
from desk.stats.replication import ReplicationFramework    
from desk.analytics.financial import FinancialAnalyzer
from desk.validation.resource_validator import ResourceValidator
from desk.core.simulation_model import SimulationModel
from desk.core.entity import Entity, EventLogger
from desk.blocks.create_block import CreateBlock
from desk.blocks.process_block import ProcessBlock, MultiProcessBlock
from desk.blocks.decide_block import DecideBlock
from desk.blocks.dispose_block import DisposeBlock
from desk.analytics.metrics import MetricsCollector
from desk.analytics.reporting import SimulationReporter
from desk.analytics.plotting import SimulationPlotter
from desk.validation.stability import StabilityAnalyzer
from desk.validation.warmup import WarmUpAnalyzer
from desk.config.simulation_config import SimulationConfig
from desk.visualization.interface import run_visualization


# ================================================================
# Each ACD model is implemented here
# ================================================================
# desk-sim -m src/cc.py --mode visualization
# desk-sim -m src/cc.py --mode single
# desk-sim -m src/cc.py --mode replications
# desk-sim -m src/cc.py --mode factorial

# ================================================================
# Desk-sim: DIST-FIT Which is the best data distribution?
# ================================================================
# desk-distfit -d src/input_data/1_int_cheg.txt --max-sample 500
# desk-distfit -d src/input_data/2_adm_conf.txt
# desk-distfit -d src/input_data/3_ato_anestetico.txt
# desk-distfit -d src/input_data/cir_p.txt
# desk-distfit -d src/input_data/cir_m.txt
# desk-distfit -d src/input_data/cir_g.txt
# desk-distfit -d src/input_data/3_pos_cir.txt



# ================================================================
# ESCOPO GLOBAL
# ================================================================
# Capacidades Padrão (Default)
DEFAULT_CAPACITIES = {
    "Enfermeiro": 3, 
    "Farmacia": 2, 
    "Tec_Enfermagem": 11, 
    "Eq_Assistencial_CTI": 1,
    "Eq_Medica": 6, 
    "Anestesista": 6, 
    "Tec_Radiologia": 2, 
    "Eq_Radiologia": 4,
    "Func_CME": 2, 
    "Eq_Higienizacao": 2
}

# ---------------------------------------------------------------
# Time-varying resource staffing schedule
# Each resource maps to a list of (start_h, end_h, capacity).
# Resources NOT listed here keep their default capacity unchanged.
# ---------------------------------------------------------------
RESOURCE_SCHEDULE = {
    "Eq_Medica": [
        ( 0,  2, 4),
        ( 2,  4, 4),   # quiet night → reduced staff
        ( 4,  6, 4),
        ( 6,  8, 6),
        ( 8, 10, 6),
        (10, 12, 6),   # peak → full team
        (12, 14, 6),
        (14, 16, 6),
        (16, 18, 4),
        (18, 20, 4),
        (20, 22, 4),
        (22, 24, 4),
    ],
    "Enfermeiro": [
        ( 0,  6, 1),
        ( 6, 18, 2),
        (18, 24, 2),
    ],
    "Tec_Enfermagem": [
        ( 0,  6, 10),
        ( 6, 18, 11),
        (18, 24, 11),
    ],
    # add other resources as needed ...
}

# ---------------------------------------------------------------
# Generic time-dependent arrival
# ---------------------------------------------------------------
ARRIVAL_SLOTS = [
    ( 0,  2, 0.035),   # 00–02h:  3.5%
    ( 2,  4, 0.009),   # 02–04h:  0.9%
    ( 4,  6, 0.010),   # 04–06h:  1.0%
    ( 6,  8, 0.186),   # 06–08h: 18.6%
    ( 8, 10, 0.111),   # 08–10h: 11.1%
    (10, 12, 0.151),   # 10–12h: 15.1%
    (12, 14, 0.108),   # 12–14h: 10.8%
    (14, 16, 0.125),   # 14–16h: 12.5%
    (16, 18, 0.106),   # 16–18h: 10.6%
    (18, 20, 0.035),   # 18–20h:  3.5%
    (20, 22, 0.063),   # 20–22h:  6.3%
    (22, 24, 0.061),   # 22–00h:  6.1%
]

# Pesos baseados na média diária real dividida pela média global (13.33)
WEEKDAY_FACTORS = {
    0: 14.74 / 13.3328,  # Segunda
    1: 15.67 / 13.3328,  # Terça
    2: 14.98 / 13.3328,  # Quarta (Base da simulação: 2025-01-01)
    3: 15.84 / 13.3328,  # Quinta
    4: 14.58 / 13.3328,  # Sexta
    5: 8.88 / 13.3328,   # Sábado (Menor volume no FDS)
    6: 8.64 / 13.3328,   # Domingo (Menor volume no FDS)
}

# ================================================================
HOURS = 60  # Time conversion factor (base time: Minutos)
DAYS = 1440
YEARS = 525600
# ================================================================


def make_time_dependent_arrival(base_dist, arrival_slots, env, num_sources=1, start_day_of_week=2):
        num_slots = len(arrival_slots)
        
        def time_dependent_arrival():
            # 1. Identifica o dia da semana atual na linha do tempo
            sim_day = int(env.now // 1440)
            current_day_of_week = (start_day_of_week + sim_day) % 7
            day_factor = WEEKDAY_FACTORS[current_day_of_week]
            
            # 2. Localiza a janela de 2 horas do dia
            current_hour = (env.now % 1440) / 60.0
            slot_fraction = arrival_slots[-1][2]
            for start_h, end_h, fraction in arrival_slots:
                if start_h <= current_hour < end_h:
                    slot_fraction = fraction
                    break
                    
            # 3. Combina os coeficientes de ajuste tempo-dependente
            k_total = (slot_fraction * num_slots) * day_factor
            
            base_val = base_dist() if callable(base_dist) else float(base_dist)
            return (base_val / num_sources) / k_total

        return time_dependent_arrival


def build_model(final_simulation_time=None, event_logger=None, verbose=True,
                        entity_filter=None, resource_filter=None,
                        event_type_filter=None, time_range=None): 
    """Build the simulation model with refactored structure.
    Args:
        event_logger: Optional event logger
        verbose: Enable event tracing
        entity_filter: Optional entity filter for tracing
        resource_filter: Optional resource filter for tracing
        event_type_filter: Optional event type filter for tracing
        time_range: Optional time range for tracing
    """    
    
    HOURS = 60  # Time conversion factor (base time: minutes)
    DAYS = 1440
    YEARS = 525600
    
    model = SimulationModel(verbose=verbose,
        entity_filter=entity_filter,
        resource_filter=resource_filter,
        event_type_filter=event_type_filter,
        time_range=time_range)  

    def truncated_lognormal(mu, sigma, min_los, max_los):       
        while True:
            x = random.lognormvariate(mu, sigma)
            if min_los <= x <= max_los:
                return x
                



    # Unidade básica para todos os tempos: minutos
    def distribution(tipo):
        # Arrival rates (per day → per minute if DAYS = 1440)
        # arrival_rate_cc  = 1/53 # per minute        

        distributions = {            
            # Arrivals            
            #'arrival_cc': random.expovariate(arrival_rate_cc),

            # 1. Aguarda cirurgia
            # '1_aguarda_CC': random.triangular(40, 160, 280),
                        
            # 1. Preparação da sala. Aviso cirúrgico (P:1,6)
            '1_aviso_cirurgico': 5,

            # 1. Montagem dos kits (materiais e medicação) (P:2)
            '1_montagem_kits': 5,

            # 1. Rec kit, Sep. Instrumentos, Check list, Org., Registro Info (P:3,4,5,8,9)
            '1_organiza_sala_e_kits': random.triangular(20, 25, 30),

            # 2. Transporte do paciente do CTI ao Centro Cirúrgico (P:11)
            '2_transporte_CTI_CC': random.triangular(20, 80, 150),

            # 2. Transporte do paciente de sua origem ao Centro Cirúrgico (P:11)
            '2_transporte_origem_CC': random.triangular(10, 15, 20),

            # 2. Admissão e Conferência do Paciente (P:12,13,14,15)
            #####################CONFERIR#######################            
            # 2_adm_conf.txt filtrado (retirada outliers: > 5 min, < 75 min)
            # '2_adm_e_conf_paciente': random.triangular(15, 25, 30),
            '2_adm_e_conf_paciente': 1/3 * (5.98926 + 7696.99 * random.betavariate(1.18591, 616.092)),

            # 2. Admissão do Paciente (P:16,17)
            # '2_adm_paciente': random.triangular(10, 15, 20),
            '2_adm_paciente': 1/3 * (5.98926 + 7696.99 * random.betavariate(1.18591, 616.092)),

            # 2. Checklist de Cirurgia Segura Físico (P:18)
            # '3_checklist_pre_cir': 5,
            '3_checklist_pre_cir': 1/3 * (5.98926 + 7696.99 * random.betavariate(1.18591, 616.092)),

            # 3. Ato Anestésico (P:19)

            # '3_ato_anestetico': random.triangular(20, 50, 90),                       
            # 3_ato_anestetico.txt filtrado (retirada outliers: > 5 min, < 90 min)
             '3_ato_anestetico':5.86479 + 2023.26 * random.betavariate(1.72019, 161.458),   

            # 3. Pr.Cirúrgico Pequeno (P:20,21,22)
            # '3_cirurgia_pequena': random.triangular(20, 70, 120),
            '3_cirurgia_pequena': random.lognormvariate(3.7377, 0.879545),

            # 3. Pr.Cirúrgico Médio (P:20,21,22)
            # '3_cirurgia_media': random.triangular(120, 180, 240),
            '3_cirurgia_media': random.gammavariate(2.2796, 45.7462),

            # 3. Pr.Cirúrgico Grande (P:20,21,22)
            # '3_cirurgia_grande': random.triangular(240, 480, 720),            
            '3_cirurgia_grande': random.lognormvariate(4.19377, 0.862757),

            # 3. Conferências e registros (P:23,24,25,26,27,28,29,30)
            # '3_conf_registros_pos_cir': random.triangular(20, 30, 40),            
            # como são equivalentes a 3 atividades, tem-se 0.7* (...), o shape nao muda.
            # 2_pos_cir.txt filtrado (retirada outliers: > 5 min, < 90 min)            
            '3_conf_registros_pos_cir': 0.7 * random.weibullvariate(16.4986, 1.4622),

            # 5. Remoção de resíduos e descarte de materiais. (P:37)
            # '5_remocao_residuos': random.triangular(5, 6, 7),
            '5_remocao_residuos': 0.15 * random.weibullvariate(16.4986, 1.4622),

            # 5. Separação de materiais sujos p/ processamento. (P:38)
            # '5_sep_mat_sujos': random.triangular(5, 8, 10),
            '5_sep_mat_sujos': 0.15 * random.weibullvariate(16.4986, 1.4622),

            # 5. Limpeza do Local. (P:39)
            '5_limpeza_local': random.triangular(10, 12, 15),

            # 6. Processamento de materiais. (P:40,41,42,43,44)
            #'6_processamento_materiais': random.triangular(20, 28, 34),

            # 4. Pós-oper Encaminha paciente para SRPA (P:31)
            '4_encaminha_srpa': random.triangular(10, 20, 30),

            # 4. Monit, Med, Permanência e av. Alta SRPA  (P:32,33,34)
            '4_monit_permanencia_alta_srpa': random.triangular(480, 1680, 2880),
            # '4_monit_permanencia_alta_srpa': random.triangular(240, 840, 1440),            

            # 4. Avaliação para Alta da SRPA (P:35)
            '4_avalia_alta_srpa': random.triangular(5, 8, 10),

            # 4. Transferência para Unidade de Internação (P:36)
            '4_transfere_internacao': random.triangular(10, 15, 20)
        }
        return distributions.get(tipo, 0.0)
    
    

    Enfermeiro = model.add_resource("Enfermeiro", 3, "regular") 
    Farmacia = model.add_resource("Farmacia", 2, "regular") 
    Tec_Enfermagem = model.add_resource("Tec_Enfermagem", 11, "regular") 
    Eq_Assistencial_CTI = model.add_resource("Eq_Assistencial_CTI", 1, "regular") 
    Eq_Medica = model.add_resource("Eq_Medica", 6, "regular")     
    Anestesista = model.add_resource("Anestesista", 6, "regular")    
    Tec_Radiologia = model.add_resource("Tec_Radiologia", 2, "regular") 
    Eq_Radiologia = model.add_resource("Eq_Radiologia", 4, "regular") 
    Func_CME = model.add_resource("Func_CME", 2, "regular") 
    Eq_Higienizacao = model.add_resource("Eq_Higienizacao", 2, "regular")
    # Tec_Enfermagem_X = model.add_resource("Tec_Enfermagem_X", 1, "regular")  
    
    # ═══════════════════════════════════════════════════════════════════════════
    # OPERATING ROOM CAPACITY GATE  —  5 concurrent patients maximum
    # ═══════════════════════════════════════════════════════════════════════════
    #
    #   P12a15 starts  →  Sala_CC seized  →  P12a15 ends  →  Sala_CC RELEASED
    #   ... (all intermediate blocks: adm, surgery, cleanup)  ← UNCONSTRAINED
    #   P39 starts     →  Sala_CC seized  →  P39 ends     →  Sala_CC RELEASED
    #
    # Between P12a15 and P39 the slot was free, allowing unlimited concurrency.
    #
    # WHY simpy.Container IS THE CORRECT TOOL
    # ─────────────────────────────────────────
    # simpy.Resource  →  request token must be released by the SAME SimPy
    #                    process that acquired it (held via 'with req:').
    #                    Each DESK block is its own process, so the token
    #                    cannot survive a block transition.
    #
    # simpy.Container →  Container.get(1)  permanently decrements the count
    #                    Container.put(1)  permanently increments the count
    #                    get/put are STATELESS one-shot events: they can occur
    #                    in completely DIFFERENT SimPy processes, spanning the
    #                    entire P12a15 → P39 chain.
    #
    # FLOW CORRECT
    # ────────────────────
    #   ... → P11a/b → [seize_sala_cc] ─(blocks if 5 rooms busy)─►
    #           → P12a15 → adm → surgery → cleanup → P39
    #           → [release_sala_cc] → discharge
    #
    # sala_cc.level (0–5) = available rooms; in_use = 5 − level  (max 5)
    # ═══════════════════════════════════════════════════════════════════════════
    sala_CC = simpy.Container(model.env, capacity=5, init=5)

    # ── Custom gateway blocks ──────────────────────────────────────────────────
    # These two thin classes are the ONLY place Sala_CC logic lives.
    # They do not interact with model.add_resource — they operate on the raw
    # simpy.Container directly, which is the correct SimPy pattern for
    # cross-block resource spanning.
    #
    # Implementation note
    # ───────────────────
    # The classes subclass ProcessBlock so they integrate naturally with DESK's
    # model.add_block(), connect_to(), and event_logger machinery.
    # They override only the entity-processing coroutine (run / _run / process —
    # whichever name your DESK build uses; see the comment inside each class).
    # ─────────────────────────────────────────────────────────────────────────

    class SalaCC_Seize(ProcessBlock):
        """
        Gateway block placed between P11a/b and adm_conf_paciente_P12a15.

        Behaviour
        ─────────
        • Calls sala_cc.get(1).  If the container level is 0 (all 5 rooms
          occupied), the entity waits here until one room becomes free.
        • Once sala_cc.get(1) succeeds, the level is decremented by 1 and
          stays decremented until the matching SalaCC_Release fires put(1).
        • Zero processing delay — the block is purely a gate, not a service.

        The slot is held for the full duration of the patient's stay
        (P12a15 through P39), not just while this block is active.
        """
        def __init__(self, name, env, container, event_logger=None):
            super().__init__(name, env, delay_time=lambda: 0.0, resource=None, event_logger=event_logger)
            self._sala_cc = container

        def process_entity(self, entity: Entity):
            entity.route_history.append(self.name)
            
            # Trace queue entry in console
            self._trace('queue', entity, "Sala_CC", f"Waiting for operating room. Available: {self._sala_cc.level}")
            
            # 1. BLOCKS the process pipeline here until a room slot becomes free
            yield self._sala_cc.get(1)
            
            # Trace successful allocation
            self._trace('service_start', entity, "Sala_CC", f"Operating room secured. Remaining: {self._sala_cc.level}")
            
            if self.event_logger:
                self.event_logger.log_event(
                    case_id=entity.id,
                    activity=self.name,
                    timestamp=self.env.now,
                    lifecycle='complete',
                    resource="Sala_CC"
                )
            
            # 2. Forward entity to the next block (adm_conf_paciente_P12a15)
            self.env.process(self.send_to_next(entity))
            yield self.env.timeout(0)

    class SalaCC_Release(ProcessBlock):
        """
        Release block placed between limpeza_organizacao_P39 and discharge_srpa.

        Behaviour
        ─────────
        • Calls sala_cc.put(1), which increments the container level back.
        • put() never blocks (capacity is always ≥ in-use count).
        • This unblocks the next patient waiting in SalaCC_Seize, if any.
        • Zero processing delay — purely a signal, not a service step.
        """
        def __init__(self, name, env, container, event_logger=None):
            super().__init__(name, env, delay_time=lambda: 0.0, resource=None, event_logger=event_logger)
            self._sala_cc = container

        def process_entity(self, entity: Entity):
            entity.route_history.append(self.name)
            
            # 1. RETURN the operating room slot back to the pool
            yield self._sala_cc.put(1)
            
            # Trace successful release
            self._trace('service_end', entity, "Sala_CC", f"Operating room released. Available: {self._sala_cc.level}")
            
            if self.event_logger:
                self.event_logger.log_event(
                    case_id=entity.id,
                    activity=self.name,
                    timestamp=self.env.now,
                    lifecycle='complete',
                    resource="Sala_CC"
                )
            
            # 2. Forward entity to the next block (e.g., discharge or recovery area)
            self.env.process(self.send_to_next(entity))
            yield self.env.timeout(0)

    # ── Instantiate the two gateway blocks ────────────────────────────────────
    seize_sala_cc = SalaCC_Seize(
        "Seize_Sala_CC", model.env,
        container=sala_CC,
        event_logger=event_logger,
    )

    release_sala_cc = SalaCC_Release(
        "Release_Sala_CC", model.env,
        container=sala_CC,
        event_logger=event_logger,
    )



    def make_resource_scheduler(env, resource_map, schedule):
        """
        Returns a SimPy generator that adjusts resource capacities at
        each slot boundary.  Run it as a background process:

            model.env.process(make_resource_scheduler(
                env=model.env,
                resource_map={
                    "Eq_Medica":      Eq_Medica,
                    "Enfermeiro":     Enfermeiro,
                    "Tec_Enfermagem": Tec_Enfermagem,
                },
                schedule=RESOURCE_SCHEDULE,
            ))

        Notes
        -----
        • Capacity *increase*: pending requests are served immediately.
        • Capacity *decrease*: in-service entities are NOT preempted;
        the lower cap takes effect as servers become free (standard
        SimPy behaviour — no extra logic needed).
        • resource._capacity is SimPy's internal attribute; there is no
        public setter in SimPy 4.x, so direct assignment is the
        accepted pattern for dynamic staffing.

        Parameters
        ----------
        env          : simpy.Environment  (model.env)
        resource_map : dict {name: simpy_resource}
        schedule     : dict {name: [(start_h, end_h, capacity), ...]}
        days         : int   minutes per simulated day (default 1440)
        """

        DAYS=1440

        def _current_capacity(slots, current_hour):
            """Return the capacity for the active slot."""
            for start_h, end_h, cap in slots:
                if start_h <= current_hour < end_h:
                    return cap
            return slots[-1][2]                         # fallback: last slot

        def _minutes_to_next_boundary(now, schedule):
            """Minutes until the nearest upcoming slot boundary."""
            day_minute = now % DAYS
            # Collect every unique boundary (in minutes) across all resources
            boundaries = sorted({
                h * 60
                for slots in schedule.values()
                for start_h, end_h, _ in slots
                for h in (start_h, end_h)
            })
            for b in boundaries:
                if b > day_minute:
                    return b - day_minute
            # Wrap around midnight to the first boundary of the next day
            return (DAYS - day_minute) + boundaries[0]

        def _scheduler():
            while True:
                current_hour = (env.now % DAYS) / 60.0

                # ── Apply capacity for every scheduled resource ────────────────
                for name, slots in schedule.items():
                    if name in resource_map:
                        new_cap = _current_capacity(slots, current_hour)
                        resource_map[name]._capacity = new_cap

                # ── Sleep until the next boundary ──────────────────────────────
                wait = _minutes_to_next_boundary(env.now, schedule)
                yield env.timeout(wait)

        return _scheduler()

    # ── Start the staffing scheduler ───────────────────────────────────────
    model.env.process(make_resource_scheduler(
        env=model.env,
        resource_map={
            "Eq_Medica":      Eq_Medica,
            "Enfermeiro":     Enfermeiro,
            "Tec_Enfermagem": Tec_Enfermagem,
        },
        schedule=RESOURCE_SCHEDULE,
    ))
    
    


    # Definindo a função que gera o atributo dinamicamente baseado na hora do relógio da simulação
    def generate_surgery_complexity():
        current_hour = (model.env.now % 1440) / 60.0
        # Turno Principal (Dia: 06h às 18h) -> Alta concentração de cirurgias planejadas (Major)
        if 6.0 <= current_hour < 18.0:
            return "Major" if random.random() < 0.85 else "Minor"
        # Turno da Noite -> Predomínio de procedimentos rápidos ou urgências (Minor)
        else:
            return "Minor" if random.random() < 0.90 else "Major"

    # 1. Criação do Bloco usando a função de chegada calibrada por hora/dia
    # (Substitua 'tempo_base_interchegada' pela sua variável de média original, ex: 45.0)
    base_dist=lambda: random.weibullvariate(101.8/3, 0.898199)  # ← time-dependent
    # base_dist=lambda: max(0,random.gauss(14,2))  # ← time-dependent
    func_chegada_dinamica = make_time_dependent_arrival(base_dist, ARRIVAL_SLOTS, model.env)

    # ============================ ACTIVITIES ====================
    # Create block
    arrivals_cc = CreateBlock(
        "Cheg_CC", model.env,        
        # inter_arrival_time=make_time_dependent_arrival(            
        #     base_dist=lambda: 1926/1292 * (1 + 6292.79 * random.betavariate(0.835686, 49.5466)),  # ← time-dependent
        #     arrival_slots=ARRIVAL_SLOTS,
        #     num_sources=5),          # ← 5 parallel CreateBlocks),
        inter_arrival_time=func_chegada_dinamica,
        entity_prefix="CC_Patient",
        max_arrivals=None, # Infinito
        first_creation=0.0,
        # priority_generator=patient_severity,
        event_logger=event_logger
    )
    # 2. Injeção Automática do Atributo no CreateBlock através do _apply_attributes interno
    # assigned_attrs
    # CORRETO:
    arrivals_cc.assign_attributes(surgery_complexity=generate_surgery_complexity)     
    
    # # # ProcessBlock block: Process with NO resource
    # delay_ag_cc = ProcessBlock(
    #     "Pac_aguarda_lib_CC", model.env,
    #     resource=Tec_Enfermagem_X,        
    #     delay_time=lambda: distribution('1_aguarda_CC'),        
    #     event_logger=event_logger
    # )
    # delay_ag_cc.set_resource_name('Tec_Enfermagem_X') 
    
    # ProcessBlock block: Process with ONE resource
    prep_sala_P16 = ProcessBlock(
        "Aviso_Cir", model.env,
        resource=Enfermeiro,        
        delay_time=lambda: distribution('1_aviso_cirurgico'),
        resource_units=1,                 
        event_logger=event_logger
    )
    prep_sala_P16.set_resource_name('Enfermeiro')

    # ProcessBlock block: Process with ONE resource
    prep_sala_P2 = ProcessBlock(
        "Monta_Kits", model.env,
        resource=Farmacia,        
        delay_time=lambda: distribution('1_montagem_kits'),
        resource_units=1,                 
        event_logger=event_logger
    )
    prep_sala_P2.set_resource_name('Farmacia') 

    # ProcessBlock block: Process with ONE resource
    prep_sala_P3a9 = ProcessBlock(
        "Org_Sala_Kits", model.env,
        resource=Tec_Enfermagem,        
        delay_time=lambda: distribution('1_organiza_sala_e_kits'),
        resource_units=1,                 
        event_logger=event_logger
    )
    prep_sala_P3a9.set_resource_name('Tec_Enfermagem') 

    # ProcessBlock block: Process with ONE resource
    adm_conf_paciente_P11a = ProcessBlock(
        "Transp_CTI_CC", model.env,
        resource=Eq_Assistencial_CTI,        
        delay_time=lambda: distribution('2_transporte_CTI_CC'),
        resource_units=1,                 
        event_logger=event_logger
    )
    adm_conf_paciente_P11a.set_resource_name('Eq_Assistencial_CTI')

    # ProcessBlock block: Process with ONE resource
    adm_conf_paciente_P11b = ProcessBlock(
        "Transp_Ori_CC", model.env,
        resource=Tec_Enfermagem,        
        delay_time=lambda: distribution('2_transporte_origem_CC'),
        resource_units=1,                 
        event_logger=event_logger
    )
    adm_conf_paciente_P11b.set_resource_name('Tec_Enfermagem')

    # ProcessBlock block: Process with ONE resource    
    adm_conf_paciente_P12a15 = ProcessBlock(
        "Adm_Conf_Pac", model.env,
        resource=Tec_Enfermagem,        
        delay_time=lambda: distribution('2_adm_e_conf_paciente'),
        resource_units=1,          
        event_logger=event_logger
    )
    adm_conf_paciente_P12a15.set_resource_name('Tec_Enfermagem')


    # ProcessBlock block: Process with ONE resource
    adm_paciente_P1617 = ProcessBlock(
        "Adm_Paciente", model.env,
        resource=Tec_Enfermagem,        
        delay_time=lambda: distribution('2_adm_paciente'),
        resource_units=1,                 
        event_logger=event_logger
    )
    adm_paciente_P1617.set_resource_name('Tec_Enfermagem')

    # ProcessBlock block: Process with ONE resource
    proc_cirurgico_P18 = ProcessBlock(
        "Check_Cir_Seg", model.env,
        resource=Eq_Medica,        
        delay_time=lambda: distribution('3_checklist_pre_cir'),
        resource_units=1,                 
        event_logger=event_logger
    )
    proc_cirurgico_P18.set_resource_name('Eq_Medica')    

    # ProcessBlock block: Process with ONE resource
    proc_cirurgico_P19 = ProcessBlock(
        "Ato_Anest", model.env,
        resource=Anestesista,        
        delay_time=lambda: distribution('3_ato_anestetico'),
        resource_units=1,                 
        event_logger=event_logger
    )
    proc_cirurgico_P19.set_resource_name('Anestesista')  

    # MultiProcessBlock block: Process with MULTIPLE resources
    # >> Atention: 25% of distribution('3_cirurgia_pequena')
    proc_cirurgico_P_P20_025 = MultiProcessBlock(
        "Cir_Pequena_025", model.env,        
        resource_requirements={                        
            Eq_Medica: 1,            
            Tec_Enfermagem: 1
        },        
        delay_time=lambda: 0.25*distribution('3_cirurgia_pequena'),        
        event_logger=event_logger
    )    
    proc_cirurgico_P_P20_025.set_resource_names({                
        Eq_Medica: 'Eq_Medica',        
        Tec_Enfermagem: 'Tec_Enfermagem'
    })  

    # MultiProcessBlock block: Process with MULTIPLE resources
    # >> Atention: 15% of distribution('3_cirurgia_pequena')
    proc_cirurgico_P_P20aP22_015 = MultiProcessBlock(
        "Cir_Pequena_015", model.env,        
        resource_requirements={            
            Anestesista: 1,
            Eq_Medica: 1,            
            Tec_Enfermagem: 1
        },        
        delay_time=lambda: 0.15*distribution('3_cirurgia_pequena'),        
        event_logger=event_logger
    )    
    proc_cirurgico_P_P20aP22_015.set_resource_names({        
        Anestesista: 'Anestesista',
        Eq_Medica: 'Eq_Medica',        
        Tec_Enfermagem: 'Tec_Enfermagem'
    })  

    # MultiProcessBlock block: Process with MULTIPLE resources
    # >> Atention: 15% of distribution('3_cirurgia_pequena')
    proc_cirurgico_P_P20aP22_015_Radio = MultiProcessBlock(
        "Cir_Pequena_015R", model.env,        
        resource_requirements={            
            Anestesista: 1,
            Eq_Medica: 1,
            Tec_Radiologia: 1,
            Eq_Radiologia: 1,
            Tec_Enfermagem: 1
        },        
        delay_time=lambda: 0.15*distribution('3_cirurgia_pequena'),        
        event_logger=event_logger
    )    
    proc_cirurgico_P_P20aP22_015_Radio.set_resource_names({        
        Anestesista: 'Anestesista',
        Eq_Medica: 'Eq_Medica',
        Tec_Radiologia: 'Tec_Radiologia',
        Eq_Radiologia: 'Eq_Radiologia',
        Tec_Enfermagem: 'Tec_Enfermagem'
    }) 

    # MultiProcessBlock block: Process with MULTIPLE resources
    # >> Atention: 60% of distribution('3_cirurgia_pequena')
    proc_cirurgico_P_P20_060 = MultiProcessBlock(
        "Cir_Pequena_060", model.env,        
        resource_requirements={                        
            Eq_Medica: 1,            
            Tec_Enfermagem: 1
        },        
        delay_time=lambda: 0.60*distribution('3_cirurgia_pequena'),        
        event_logger=event_logger
    )    
    proc_cirurgico_P_P20_060.set_resource_names({                
        Eq_Medica: 'Eq_Medica',        
        Tec_Enfermagem: 'Tec_Enfermagem'
    })

    # MultiProcessBlock block: Process with MULTIPLE resources
    # >> Atention: 25% of distribution('3_cirurgia_media')
    proc_cirurgico_M_P20_025 = MultiProcessBlock(
        "Cir_Media_025", model.env,        
        resource_requirements={                        
            Eq_Medica: 1,            
            Tec_Enfermagem: 1
        },        
        delay_time=lambda: 0.25*distribution('3_cirurgia_media'),        
        event_logger=event_logger
    )    
    proc_cirurgico_M_P20_025.set_resource_names({        
        Eq_Medica: 'Eq_Medica',        
        Tec_Enfermagem: 'Tec_Enfermagem'
    })

    # MultiProcessBlock block: Process with MULTIPLE resources
    # >> Atention: 15% of distribution('3_cirurgia_media')
    proc_cirurgico_M_P20aP22_015 = MultiProcessBlock(
        "Cir_Media_015", model.env,        
        resource_requirements={            
            Anestesista: 1,
            Eq_Medica: 1,            
            Tec_Enfermagem: 1
        },        
        delay_time=lambda: 0.15*distribution('3_cirurgia_media'),        
        event_logger=event_logger
    )    
    proc_cirurgico_M_P20aP22_015.set_resource_names({        
        Anestesista: 'Anestesista',
        Eq_Medica: 'Eq_Medica',        
        Tec_Enfermagem: 'Tec_Enfermagem'
    })

    # MultiProcessBlock block: Process with MULTIPLE resources
    # >> Atention: 15% of distribution('3_cirurgia_media')
    proc_cirurgico_M_P20aP22_015_Radio = MultiProcessBlock(
        "Cir_Media_015R", model.env,        
        resource_requirements={            
            Anestesista: 1,
            Eq_Medica: 1,
            Tec_Radiologia: 1,
            Eq_Radiologia: 1,
            Tec_Enfermagem: 1
        },        
        delay_time=lambda: 0.15*distribution('3_cirurgia_media'),        
        event_logger=event_logger
    )    
    proc_cirurgico_M_P20aP22_015_Radio.set_resource_names({        
        Anestesista: 'Anestesista',
        Eq_Medica: 'Eq_Medica',
        Tec_Radiologia: 'Tec_Radiologia',
        Eq_Radiologia: 'Eq_Radiologia',
        Tec_Enfermagem: 'Tec_Enfermagem'
    })

    # MultiProcessBlock block: Process with MULTIPLE resources
    # >> Atention: 60% of distribution('3_cirurgia_media')
    proc_cirurgico_M_P20_060 = MultiProcessBlock(
        "Cir_Media_060", model.env,        
        resource_requirements={                        
            Eq_Medica: 1,            
            Tec_Enfermagem: 1
        },        
        delay_time=lambda: 0.60*distribution('3_cirurgia_media'),        
        event_logger=event_logger
    )    
    proc_cirurgico_M_P20_060.set_resource_names({        
        Eq_Medica: 'Eq_Medica',        
        Tec_Enfermagem: 'Tec_Enfermagem'
    })

    # MultiProcessBlock block: Process with MULTIPLE resources
    # >> Atention: 25% of distribution('3_cirurgia_grande')
    proc_cirurgico_G_P20_025 = MultiProcessBlock(
        "Cir_Grande_025", model.env,        
        resource_requirements={                        
            Eq_Medica: 1,            
            Tec_Enfermagem: 1
        },        
        delay_time=lambda: 0.25*distribution('3_cirurgia_grande'),        
        event_logger=event_logger
    )    
    proc_cirurgico_G_P20_025.set_resource_names({                
        Eq_Medica: 'Eq_Medica',        
        Tec_Enfermagem: 'Tec_Enfermagem'
    })

    # MultiProcessBlock block: Process with MULTIPLE resources
    # >> Atention: 15% of distribution('3_cirurgia_grande')
    proc_cirurgico_G_P20aP22_015 = MultiProcessBlock(
        "Cir_Grande_015", model.env,        
        resource_requirements={            
            Anestesista: 1,
            Eq_Medica: 1,            
            Tec_Enfermagem: 1
        },        
        delay_time=lambda: 0.15*distribution('3_cirurgia_grande'),        
        event_logger=event_logger
    )    
    proc_cirurgico_G_P20aP22_015.set_resource_names({        
        Anestesista: 'Anestesista',
        Eq_Medica: 'Eq_Medica',        
        Tec_Enfermagem: 'Tec_Enfermagem'
    })

    # MultiProcessBlock block: Process with MULTIPLE resources
    # >> Atention: 15% of distribution('3_cirurgia_grande')
    proc_cirurgico_G_P20aP22_015_Radio = MultiProcessBlock(
        "Cir_Grande_015R", model.env,        
        resource_requirements={            
            Anestesista: 1,
            Eq_Medica: 1,
            Tec_Radiologia: 1,
            Eq_Radiologia: 1,
            Tec_Enfermagem: 1
        },        
        delay_time=lambda: 0.15*distribution('3_cirurgia_grande'),        
        event_logger=event_logger
    )    
    proc_cirurgico_G_P20aP22_015_Radio.set_resource_names({        
        Anestesista: 'Anestesista',
        Eq_Medica: 'Eq_Medica',
        Tec_Radiologia: 'Tec_Radiologia',
        Eq_Radiologia: 'Eq_Radiologia',
        Tec_Enfermagem: 'Tec_Enfermagem'
    })

    # MultiProcessBlock block: Process with MULTIPLE resources
    # >> Atention: 60% of distribution('3_cirurgia_grande')
    proc_cirurgico_G_P20_060 = MultiProcessBlock(
        "Cir_Grande_060", model.env,        
        resource_requirements={                        
            Eq_Medica: 1,            
            Tec_Enfermagem: 1
        },        
        delay_time=lambda: 0.60*distribution('3_cirurgia_grande'),        
        event_logger=event_logger
    )    
    proc_cirurgico_G_P20_060.set_resource_names({                
        Eq_Medica: 'Eq_Medica',        
        Tec_Enfermagem: 'Tec_Enfermagem'
    })


    # MultiProcessBlock block: Process with MULTIPLE resources
    proc_cirurgico_pos_P23aP30 = MultiProcessBlock(
        "Conf_Registros", model.env,        
        resource_requirements={            
            Anestesista: 1,
            Eq_Medica: 1,
            #Tec_Radiologia: 1,            
            Tec_Enfermagem: 1
        },        
        delay_time=lambda: distribution('3_conf_registros_pos_cir'),        
        event_logger=event_logger
    )    
    proc_cirurgico_pos_P23aP30.set_resource_names({        
        Anestesista: 'Anestesista',
        Eq_Medica: 'Eq_Medica',
        #Tec_Radiologia: 'Tec_Radiologia',        
        Tec_Enfermagem: 'Tec_Enfermagem'
    })
    
    # ProcessBlock block: Process with ONE resource
    limpeza_organizacao_P37 = ProcessBlock(
        "Remov_Residuos", model.env,
        resource=Tec_Enfermagem,        
        delay_time=lambda: distribution('5_remocao_residuos'),
        resource_units=1,                 
        event_logger=event_logger
    )
    limpeza_organizacao_P37.set_resource_name('Tec_Enfermagem') 

    # ProcessBlock block: Process with ONE resource
    limpeza_organizacao_P38 = ProcessBlock(
        "Sep_MatSujo", model.env,
        resource=Func_CME,        
        delay_time=lambda: distribution('5_sep_mat_sujos'),
        resource_units=1,                 
        event_logger=event_logger
    )
    limpeza_organizacao_P38.set_resource_name('Func_CME')

    # ProcessBlock block: Process with ONE resource
    limpeza_organizacao_P39 = ProcessBlock(
        "Limpa_Sala_CC", model.env,
        resource=Eq_Higienizacao,        
        delay_time=lambda: distribution('5_limpeza_local'),
        resource_units=1,                 
        event_logger=event_logger
    )
    limpeza_organizacao_P39.set_resource_name('Eq_Higienizacao')
   
    
    # MultiProcessBlock block: Process with MULTIPLE resources
    #proc_materiais_P40aP44 = MultiProcessBlock(
    #    "Proc_Mat_Sujos", model.env,        
    #    resource_requirements={            
    #        Tec_Enfermagem: 1,            
    #        Func_CME: 1
    #    },        
    #    delay_time=lambda: distribution('6_processamento_materiais'),        
    #    event_logger=event_logger
    #)    
    #proc_materiais_P40aP44.set_resource_names({        
    #    Tec_Enfermagem: 'Tec_Enfermagem',       
    #    Func_CME: 'Func_CME'
    #})

    # # ProcessBlock block: Process with NO resource
    # ps_prepare = ProcessBlock(
    #     "PS prepara Encaminhamento", model.env,        
    #     delay_time=lambda: distribution('ps_prepare'),        
    #     event_logger=event_logger
    # )    
    # ============================================================
    
    # ============================ DECISIONS ==================== 
    arriv_CC_busy_decision = DecideBlock(
        "CC_busy", model.env,
        decision_type="condition_generic",
        event_logger=event_logger
    )

    origem_paciente_decision = DecideBlock(
        "Origem_Paciente", model.env,
        decision_type="probability",
        event_logger=event_logger
    )

    porte_cirurgia_decision = DecideBlock(
        "Porte_Cir", model.env,
        decision_type="condition_generic",
        event_logger=event_logger
    )    

    faz_ex_radio_cir_p_decision = DecideBlock(
        "Faz_Rad_Cir_P", model.env,
        decision_type="probability",
        event_logger=event_logger
    )

    faz_ex_radio_cir_m_decision = DecideBlock(
        "Faz_Rad_Cir_M", model.env,
        decision_type="probability",
        event_logger=event_logger
    )

    faz_ex_radio_cir_g_decision = DecideBlock(
        "Faz_Rad_Cir_G", model.env,
        decision_type="probability",
        event_logger=event_logger
    )
    # ============================================================

    
    # ============================ DISPOSALS ====================            
    discharge_arrival = DisposeBlock("Saida_CC_Busy", model.env, event_logger=event_logger)     
    discharge_srpa = DisposeBlock("Saida_SRPA", model.env, event_logger=event_logger)     
    # ============================================================

    # ============================ INCLUDE ALL BLOCKS ====================    
    # Add blocks to model
    for block in [arrivals_cc, arriv_CC_busy_decision,
                #   delay_ag_cc, 
                  discharge_arrival, 
                  seize_sala_cc,
                  prep_sala_P16, prep_sala_P2, prep_sala_P3a9,
                  origem_paciente_decision, 
                  adm_conf_paciente_P11a,                   
                  adm_conf_paciente_P11b,                   
                  adm_conf_paciente_P12a15, adm_paciente_P1617, 
                  proc_cirurgico_P18, proc_cirurgico_P19, 
                  porte_cirurgia_decision,
                  faz_ex_radio_cir_p_decision, faz_ex_radio_cir_m_decision, faz_ex_radio_cir_g_decision,
                  proc_cirurgico_P_P20_025, proc_cirurgico_P_P20aP22_015, proc_cirurgico_P_P20aP22_015_Radio, proc_cirurgico_P_P20_060, 
                  proc_cirurgico_M_P20_025, proc_cirurgico_M_P20aP22_015, proc_cirurgico_M_P20aP22_015_Radio, proc_cirurgico_M_P20_060, 
                  proc_cirurgico_G_P20_025, proc_cirurgico_G_P20aP22_015, proc_cirurgico_G_P20aP22_015_Radio, proc_cirurgico_G_P20_060,
                  proc_cirurgico_pos_P23aP30,
                  limpeza_organizacao_P37, limpeza_organizacao_P38, limpeza_organizacao_P39,
                  release_sala_cc,
                  discharge_srpa
                  ]:
        model.add_block(block)
    # ====================================================================
    
    # ============================ CONNECT ALL BLOCKS ====================    
    # arrivals_cc.connect_to(prep_sala_P16)
    # arrivals_cc.connect_to(seize_sala_cc)
    arrivals_cc.connect_to(arriv_CC_busy_decision)

    arriv_CC_busy_decision.add_route("Pac_Entra_CC", seize_sala_cc, 
        condition_generic=lambda e, ctx: sala_CC.level > 0)
        
    # arriv_CC_busy_decision.add_route("Pac_Ag_CC", delay_ag_cc, 
    #     condition_generic=lambda e, ctx: True) # Catch-all fallback (else)

    # arriv_CC_busy_decision.add_route("Pac_Ag_CC", delay_ag_cc, 
    #     condition_generic=lambda e, ctx: len(Tec_Enfermagem_X.queue) < 2) # (then)
    
    # delay_ag_cc.connect_to(arriv_CC_busy_decision)

    arriv_CC_busy_decision.add_route("Pac_Sai_CC", discharge_arrival, 
        condition_generic=lambda e, ctx: True) # Catch-all fallback (else)
    
    
    
    seize_sala_cc.connect_to(prep_sala_P16)
    prep_sala_P16.connect_to(prep_sala_P2)
    prep_sala_P2.connect_to(prep_sala_P3a9)
    prep_sala_P3a9.connect_to(origem_paciente_decision)

    origem_paciente_decision.add_route("Pac_CTI", adm_conf_paciente_P11a, probability=0.071)
    origem_paciente_decision.add_route("Pac_Outros", adm_conf_paciente_P11b, probability=0.929)

    adm_conf_paciente_P11a.connect_to(adm_conf_paciente_P12a15)    
    adm_conf_paciente_P11b.connect_to(adm_conf_paciente_P12a15)            
    adm_conf_paciente_P12a15.connect_to(adm_paciente_P1617)
    adm_paciente_P1617.connect_to(proc_cirurgico_P18)
    proc_cirurgico_P18.connect_to(proc_cirurgico_P19)
    proc_cirurgico_P19.connect_to(porte_cirurgia_decision)



    # porte_cirurgia_decision.add_route("Cir Pequeno", proc_cirurgico_P_P20_025, probability=0.4)
    # porte_cirurgia_decision.add_route("Cir Medio", proc_cirurgico_M_P20_025, probability=0.4)
    # porte_cirurgia_decision.add_route("Cir Grande", proc_cirurgico_G_P20_025, probability=0.2)

    # def assign_shift(dt):
    #     hour = dt.hour
    #     if 7 <= hour < 13: return "Manhã"
    #     elif 13 <= hour < 19: return "Tarde"
    #     else: return "Noite"

    # Turno           Pequeno Médio (condicional) Grande  Total
    # Diurno (7h-19h) 15%     50%                 35%     100%
    # Noturno         80%     15%                 5%      100%

    porte_cirurgia_decision.add_route("Cir Pequeno", proc_cirurgico_P_P20_025, 
    # Cirurgias pequenas ocorrem 15% entre 7h e 19h, e 80% depois de 18h
        condition_generic=lambda e, ctx: (
            random.random() < 0.15 if 7.0 <= (ctx['time'] % 1440) / 60.0 < 19.0 
            else random.random() < 0.80
        ))
    porte_cirurgia_decision.add_route("Cir Medio", proc_cirurgico_M_P20_025, 
    # Cirurgias médias ocorrem 53% entre 7h e 19h, de 75% depois de 18h
        condition_generic=lambda e, ctx: (
            random.random() < 0.70 if 7.0 <= (ctx['time'] % 1440) / 60.0 < 19.0 
            else random.random() < 0.15  # Proporção ajustada considerando o resíduo do fluxo anterior
        ))
    porte_cirurgia_decision.add_route("Cir Grande", proc_cirurgico_G_P20_025, 
        condition_generic=lambda e, ctx: True)





    # ====================
    proc_cirurgico_P_P20_025.connect_to(faz_ex_radio_cir_p_decision)

    faz_ex_radio_cir_p_decision.add_route("Cir_P_Sem_Radio", proc_cirurgico_P_P20aP22_015, probability=0.95)
    faz_ex_radio_cir_p_decision.add_route("Cir_P_Com_Radio", proc_cirurgico_P_P20aP22_015_Radio, probability=0.05)

    proc_cirurgico_P_P20aP22_015.connect_to(proc_cirurgico_P_P20_060)
    proc_cirurgico_P_P20aP22_015_Radio.connect_to(proc_cirurgico_P_P20_060)

    # ====================
    proc_cirurgico_M_P20_025.connect_to(faz_ex_radio_cir_m_decision)

    faz_ex_radio_cir_m_decision.add_route("Cir_M_Sem_Radio", proc_cirurgico_M_P20aP22_015, probability=0.80)
    faz_ex_radio_cir_m_decision.add_route("Cir_M_Com_Radio", proc_cirurgico_M_P20aP22_015_Radio, probability=0.20)

    proc_cirurgico_M_P20aP22_015.connect_to(proc_cirurgico_M_P20_060)
    proc_cirurgico_M_P20aP22_015_Radio.connect_to(proc_cirurgico_M_P20_060)
    # ====================

    proc_cirurgico_G_P20_025.connect_to(faz_ex_radio_cir_g_decision)

    faz_ex_radio_cir_g_decision.add_route("Cir_G_Sem_Radio", proc_cirurgico_G_P20aP22_015, probability=0.60)
    faz_ex_radio_cir_g_decision.add_route("Cir_G_Com_Radio", proc_cirurgico_G_P20aP22_015_Radio, probability=0.40)

    proc_cirurgico_G_P20aP22_015.connect_to(proc_cirurgico_G_P20_060)
    proc_cirurgico_G_P20aP22_015_Radio.connect_to(proc_cirurgico_G_P20_060)
    # ====================

    proc_cirurgico_P_P20_060.connect_to(proc_cirurgico_pos_P23aP30)
    proc_cirurgico_M_P20_060.connect_to(proc_cirurgico_pos_P23aP30)
    proc_cirurgico_G_P20_060.connect_to(proc_cirurgico_pos_P23aP30)

    proc_cirurgico_pos_P23aP30.connect_to(limpeza_organizacao_P37)  
    

    limpeza_organizacao_P37.connect_to(limpeza_organizacao_P38)
    limpeza_organizacao_P38.connect_to(limpeza_organizacao_P39)
    limpeza_organizacao_P39.connect_to(release_sala_cc)
    release_sala_cc.connect_to(discharge_srpa)
    # limpeza_organizacao_P39.connect_to(discharge_srpa)

    #proc_materiais_P40aP44.connect_to(discharge_srpa)
    

    # ================================================================
    # CONFIGURE FINANCIAL ATTRIBUTES
    # ================================================================    
    # Assign costs to each activity
    arrivals_cc.assign_attributes(
        cost=lambda: random.uniform(20, 30)  # costs $20-30
    )
    # Assign costs to each activity
    prep_sala_P16.assign_attributes(
        cost=lambda: random.uniform(20, 30)  # costs $20-30
    ) 
     # Assign costs to each activity
    prep_sala_P2.assign_attributes(
        cost=lambda: random.uniform(20, 30)  # costs $20-30
    )    
     # Assign costs to each activity
    prep_sala_P3a9.assign_attributes(
        cost=lambda: random.uniform(20, 30)  # costs $20-30
    ) 
     # Assign costs to each activity
    adm_conf_paciente_P11a.assign_attributes(
        cost=lambda: random.uniform(20, 30)  # costs $20-30
    ) 
     # Assign costs to each activity
    adm_conf_paciente_P11b.assign_attributes(
        cost=lambda: random.uniform(20, 30)  # costs $20-30
    ) 
     # Assign costs to each activity
    adm_conf_paciente_P12a15.assign_attributes(
        cost=lambda: random.uniform(20, 30)  # costs $20-30
    ) 
     # Assign costs to each activity
    adm_paciente_P1617.assign_attributes(
        cost=lambda: random.uniform(20, 30)  # costs $20-30
    ) 
     # Assign costs to each activity
    proc_cirurgico_P18.assign_attributes(
        cost=lambda: random.uniform(20, 30)  # costs $20-30
    ) 
     # Assign costs to each activity
    proc_cirurgico_P19.assign_attributes(
        cost=lambda: random.uniform(20, 30)  # costs $20-30
    ) 
    # =======================
    # Assign costs to each activity
    proc_cirurgico_P_P20_025.assign_attributes(
        cost=lambda: random.uniform(50, 100)  # Surgery costs $100-200
    )
    # Assign costs to each activity
    proc_cirurgico_P_P20aP22_015.assign_attributes(
        cost=lambda: random.uniform(100, 200)  # Surgery costs $100-200
    )
    # Assign costs to each activity
    proc_cirurgico_P_P20aP22_015_Radio.assign_attributes(
        cost=lambda: random.uniform(110, 210)  # Surgery costs $100-200
    )
    # Assign costs to each activity
    proc_cirurgico_P_P20_060.assign_attributes(
        cost=lambda: random.uniform(80, 110)  # Surgery costs $100-200
    )
    # =======================
    # =======================
    # Assign costs to each activity
    proc_cirurgico_M_P20_025.assign_attributes(
        cost=lambda: random.uniform(50, 100)  # Surgery costs $100-200
    )
    # Assign costs to each activity
    proc_cirurgico_M_P20aP22_015.assign_attributes(
        cost=lambda: random.uniform(100, 200)  # Surgery costs $100-200
    )
    # Assign costs to each activity
    proc_cirurgico_M_P20aP22_015_Radio.assign_attributes(
        cost=lambda: random.uniform(110, 210)  # Surgery costs $100-200
    )
    # Assign costs to each activity
    proc_cirurgico_M_P20_060.assign_attributes(
        cost=lambda: random.uniform(80, 110)  # Surgery costs $100-200
    )
    # =======================
    # =======================
    # Assign costs to each activity
    proc_cirurgico_G_P20_025.assign_attributes(
        cost=lambda: random.uniform(50, 100)  # Surgery costs $100-200
    )
    # Assign costs to each activity
    proc_cirurgico_G_P20aP22_015.assign_attributes(
        cost=lambda: random.uniform(100, 200)  # Surgery costs $100-200
    )
    # Assign costs to each activity
    proc_cirurgico_G_P20aP22_015_Radio.assign_attributes(
        cost=lambda: random.uniform(110, 210)  # Surgery costs $100-200
    )
    # Assign costs to each activity
    proc_cirurgico_G_P20_060.assign_attributes(
        cost=lambda: random.uniform(80, 110)  # Surgery costs $100-200
    )
    # =======================

    # Assign costs to each activity
    limpeza_organizacao_P37.assign_attributes(
        cost=lambda: random.uniform(20, 30)  # costs $20-30
    ) 
    # Assign costs to each activity
    limpeza_organizacao_P38.assign_attributes(
        cost=lambda: random.uniform(20, 30)  # costs $20-30
    ) 
    # Assign costs to each activity
    limpeza_organizacao_P39.assign_attributes(
        cost=lambda: random.uniform(20, 30)  # costs $20-30
    ) 
    # Assign costs to each activity
    #proc_materiais_P40aP44.assign_attributes(
    #    cost=lambda: random.uniform(20, 30)  # costs $20-30
    #) 
    
    # Assign revenue at discharge (based on patient complexity)
    def calculate_revenue():
        """Revenue varies by patient complexity"""
        return random.uniform(400, 500)
    
    discharge_srpa.assign_attributes(revenue=calculate_revenue)                
    # ================================================================
    
    return model


def simulation_wrapper(seed=None, until=None, warm_up_period=None):
    """Wrapper function for replication framework."""
    
    from desk.core.entity import EventLogger
    
    event_logger = EventLogger()

    HOURS = 60  # Time conversion factor (base time: minutes)
    DAYS = 1440
    YEARS = 525600

    # Create configuration
    config = SimulationConfig(
        duration=365*DAYS,
        warm_up_period=30*DAYS,        
        seed=123,
        check_stability=True
    )

    # model = build_model(event_logger)
    model = build_model(config.duration, event_logger, verbose=False)    
    
    # model.run_simulation(
    #     until=until or 24*60,
    #     seed=seed,
    #     warm_up_period=warm_up_period or 2*60
    # )
    model.run_simulation(
        validate_resources=False,
        until=until,
        seed=seed,
        warm_up_period=warm_up_period
    )
    
    return model

# ================================================================
# For full simulation
# ================================================================
# Run replications
def run_replications():
    replication_framework = ReplicationFramework(
        simulation_function=simulation_wrapper,
        n_replications=30
    )

    HOURS = 60  # Time conversion factor (base time: minutes)
    DAYS = 1440
    YEARS = 525600
    
    replication_framework.run_replications(
        base_seed=12345,
        # until=365*DAYS,
        # warm_up_period=30*DAYS
        until=36*DAYS,
        warm_up_period=3*DAYS
    )

    # Access results
    df = replication_framework.get_results_dataframe()
    print(df.describe())
# ================================================================
    

# ================================================================
# Factorial Analysis
# ================================================================
def factorial_analysis():
    """Example of factorial analysis with hospital simulation."""

    HOURS = 60  # Time conversion factor (base time: minutes)
    DAYS = 1440
    YEARS = 525600
    
    # Define simulation function wrapper
    def simulation_wrapper(arrival_rate=12, Eq_Medica=4, 
                                    seed=None, until=None, warm_up_period=0, verbose=False, **kwargs):
        """Wrapper that adapts parameters for factorial analysis."""

        # ############################################################
        # # O modelo de simulação é importado aqui
        # ############################################################
        
        # This would need to be modified in your actual model to accept these parameters
        # For now, this is a template showing how to structure it
        model = build_model(verbose=False)
        model.run_simulation(validate_resources=False, until=until, seed=seed, warm_up_period=warm_up_period)
        return model
    
    # Create factorial analysis
    factorial = FactorialExperiment(
        simulation_function=simulation_wrapper,
        base_seed=12345
    )
    
    # Add factors
    factorial.add_factor(
        factor_name='arrival_rate',
        parameter_path='CreateBlock.inter_arrival_time',
        levels=[10, 12, 14],  # Minutes between arrivals
        description='Intervalo entre chegadas de pacientes (min)'
    )
    
    # factorial.add_factor(
    #     factor_name='num_physicians',
    #     parameter_path='Resource.physicians.capacity',
    #     levels=[1, 5, 10],
    #     description='Número de médicos'
    # )

    factorial.add_factor(
        factor_name='num_Eq_Medica',
        parameter_path='Resource.Eq_Medica.capacity',
        levels=[3, 4, 5],
        description='Número de equipes Medicas'
    )
    
    # factorial.add_factor(
    #     factor_name='num_nurses',
    #     parameter_path='Resource.nurses.capacity',
    #     levels=[8, 10, 12],
    #     description='Número de enfermeiros'
    # )
    
    # Run experiment
    factorial.run_factorial_experiment(
        n_replications=5,
        # simulation_time=365*DAYS,  # 40 hours
        # warm_up_period=30*DAYS,    # 7 hours
        simulation_time=36*DAYS,  # 40 hours
        warm_up_period=3*DAYS,    # 7 hours
        verbose=True
    )
    
    # Analyze results
    factorial.print_summary()
    factorial.plot_correlation_matrix()
    factorial.plot_main_effects('system_time_avg')
    factorial.plot_interaction_effects('system_time_avg', 'arrival_rate', 'num_Eq_Medica')
    
    # Export
    factorial.export_results()

    print("\n\nFactorial analysis examples completed!")
    print("Check the generated CSV files and plots for detailed results.")
    
    return factorial
# ================================================================

def pause_simulation(message="Continue? (Enter=yes / n=no): "):
    answer = input(message)
    if answer.lower().startswith('n'):
        print(f"Simulation stopped!")
        sys.exit()  # stops the simulation


def main():
    """Main example demonstrating refactored usage."""
    
    HOURS = 60  # Time conversion factor (base time: Minutos)
    DAYS = 1440
    YEARS = 525600
    
    # Create event logger
    event_logger = EventLogger()
    
    # Build model
    print("Building Detailed CC model...")

    # Create configuration
    config = SimulationConfig(
        # warm_up_period=0
        # until=20
        # duration=24*HOURS,
        # warm_up_period=2*HOURS,
        duration=36*DAYS,
        warm_up_period=3*DAYS,        
        seed=321,
        check_stability=True
    )
    config.validate()
    
    # model = build_model(event_logger)
    # model = build_model(config.duration, event_logger, verbose=True)
    model = build_model(config.duration, event_logger, verbose=False)
    
    
    # Check stability BEFORE running (optional)
    print("\nChecking system stability...")
    stability_analyzer = StabilityAnalyzer(model)
    stability = stability_analyzer.check_system_stability()
    model.stability_result = stability
    
    # Run simulation
    print("\nRunning simulation (replication)...")
    model.run_simulation(
        validate_resources=True,  # Default True
        until=config.duration,
        seed=config.seed,
        warm_up_period=config.warm_up_period
    )
    
    
    # # === ANALYSIS PHASE (using separate modules) ===
    # #     
    # # ========================================
    # # Trace specific patient
    # # ========================================    
    # print("\n" + "="*80)
    # print("FILTER: Journey of CC_Patient_1")
    # print("="*80)    
    # pause_simulation()
    # model.trace_entity('CC_Patient_1')        
    
    # # ========================================
    # # Replay with filters
    # # ========================================
    # print("\n" + "="*80)
    # print("FILTER: Replay - First 3 patients only")
    # print("="*80)    
    # pause_simulation()
    # model.replay_trace(entity_pattern = r'^Patient_[1-3]$')
    
    # # ========================================
    # # Trace specific resource
    # # ========================================
    # print("\n" + "="*80)
    # print("FILTER: Replay - CC Tec_Enfermagem interactions only")
    # print("="*80)    
    # pause_simulation()
    # model.replay_trace(resource_filter={'Tec_Enfermagem'})
    
    # # ========================================
    # # Trace specific event types
    # # ========================================
    # print("\n" + "="*80)
    # print("FILTER: Replay - Queue and service events only")
    # print("="*80)    
    # pause_simulation()
    # model.replay_trace(event_type_filter={'queue', 'service_start', 'service_end'})
    
    # # ========================================
    # # Trace time window
    # # ========================================
    # print("\n" + "="*80)
    # print("FILTER: Replay - Events between t=20 and t=40")
    # print("="*80)    
    # pause_simulation()
    # model.replay_trace(time_range=(20, 40))
    
    # # ========================================
    # # Combined filters
    # # ========================================
    # print("\n" + "="*80)
    # print("FILTER: Replay - Patient_1 at physicians (queue + service)")
    # print("="*80)    
    # pause_simulation()
    # model.replay_trace(
    #     entity_filter={'Patient_1'},
    #     resource_filter={'physicians'},
    #     event_type_filter={'queue', 'service_start', 'service_end'}
    # )    

    # # ========================================
    # # Multiple patient journeys
    # # ========================================
    # print("\n" + "="*80)
    # print("FILTER: Detailed journeys of first 3 patients")
    # print("="*80)    
    # pause_simulation()
    # model.trace_entities(['Patient_1', 'Patient_2', 'Patient_3'])
    
    # ========================================
    # Trace statistics
    # ========================================
    model.print_trace_statistics()
    pause_simulation()

        
    print("\n" + "="*60)
    print("SIMULATION COMPLETE - ANALYZING RESULTS")
    print("="*60)
    
    # 2. Detailed reporting
    reporter = SimulationReporter(model)
    reporter.print_results()
    
    # 3. Warm-up analysis
    print("\nAnalyzing warm-up period...")
    warmup_analyzer = WarmUpAnalyzer(model)
    warmup_analyzer.analyze_warm_up_period()
    
    # 4. Plotting
    print("\nPlotting resourse use over time...")
    plotter = SimulationPlotter(model)
    
    # Plot resource utilization over time
    # plotter.plot_resource_use_over_time(show_warm_up=True, resource='nursingTech', moving_average_window=50)
    # plotter.plot_resource_use_over_time(show_warm_up=True, resource='nurses', moving_average_window=50)
    # plotter.plot_resource_use_over_time(show_warm_up=True, resource='physicians', moving_average_window=50)
    # plotter.plot_resource_use_over_time(show_warm_up=True, resource='psBeds', moving_average_window=50)
    # plotter.plot_resource_use_over_time(show_warm_up=True, resource='eMulti', moving_average_window=50)
    plotter.plot_resource_use_over_time(show_warm_up=True, resource='Enfermeiro', moving_average_window=50)
    plotter.plot_resource_use_over_time(show_warm_up=True, resource='Farmacia', moving_average_window=50)
    plotter.plot_resource_use_over_time(show_warm_up=True, resource='Tec_Enfermagem', moving_average_window=50)
    plotter.plot_resource_use_over_time(show_warm_up=True, resource='Eq_Assistencial_CTI', moving_average_window=50)
    plotter.plot_resource_use_over_time(show_warm_up=True, resource='Eq_Medica', moving_average_window=50)
    plotter.plot_resource_use_over_time(show_warm_up=True, resource='Anestesista', moving_average_window=50)
    plotter.plot_resource_use_over_time(show_warm_up=True, resource='Tec_Radiologia', moving_average_window=50)
    plotter.plot_resource_use_over_time(show_warm_up=True, resource='Func_CME', moving_average_window=50)
    plotter.plot_resource_use_over_time(show_warm_up=True, resource='Eq_Higienizacao', moving_average_window=50)
    plotter.plot_resource_use_over_time(show_warm_up=True, resource='sala_CC', moving_average_window=50)
    plotter.plot_wip_over_time()
    plotter.plot_system_time_distribution()
    # plotter.plot_system_time_distribution_filtered()
    

    # Plot activity metrics
    print("\nPlotting activity metrics...")
    reporter._print_activity_metrics()
    plotter.plot_activity_metrics()

        
    # Plot resource utilization summary
    print("\nPlotting resourse summary...")
    plotter.plot_resources_utilization()
    reporter._print_resource_metrics()
    reporter._print_entity_counts()
    reporter._print_block_statistics()

    
    # Financial analysis
    print("\nPlotting financial analysys...")
    financial_analyzer = FinancialAnalyzer(model)
    financial_analyzer.print_financial_summary()
    financial_analyzer.plot_financial_breakdown()

    # 5. Export event log
    print("\nExporting event log...")
    df = event_logger.export_to_csv("results/cc_event_log.csv")
    print(f"\nFirst 10 events:")
    print(df.head(10))
    
    # 6. Direct metrics access (if needed)
    metrics = MetricsCollector(model)
    entity_metrics = metrics.get_entity_metrics_summary()
    resource_metrics = metrics.get_resource_metrics_summary()
    
    print(f"\nAverage system time: {entity_metrics['tempo_medio_sistema']:.2f} min")
    # print(f"Nurses utilization: "
    #       f"{resource_metrics['nurses']['taxa_utilizacao']:.1%}")
    print(f"Random seed for this run: {config.seed}")
    
    return model, event_logger













# ========================================================================================
# CHARTS
# ========================================================================================
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
INPUT_FILE      = "results/cc_event_log.csv"      
OUTPUT_HTML     = "results/cc_event_log_dashboard.html"
SIM_DURATION    = 50_000                  
BASE_DATETIME   = pd.Timestamp("2025-01-01 03:00:00")  

# # Capacidades Padrão (Default)
# DEFAULT_CAPACITIES = {
#     "Enfermeiro": 3, "Farmacia": 2, "Tec_Enfermagem": 11, "Eq_Assistencial_CTI": 1,
#     "Eq_Medica": 6, "Anestesista": 6, "Tec_Radiologia": 2, "Eq_Radiologia": 4,
#     "Func_CME": 2, "Eq_Higienizacao": 2
# }

# # Escala de dimensionamento dinâmico por hora do dia
# RESOURCE_SCHEDULE = {
#     "Eq_Medica": [
#         (0, 2, 4), (2, 4, 4), (4, 6, 6), (6, 8, 6), (8, 10, 6), (10, 12, 6),
#         (12, 14, 6), (14, 16, 6), (16, 18, 6), (18, 20, 4), (20, 22, 4), (22, 24, 4)
#     ],
#     "Enfermeiro": [(0, 6, 1), (6, 18, 2), (18, 24, 2)],
#     "Tec_Enfermagem": [(0, 6, 10), (6, 18, 11), (18, 24, 11)]
# }

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







# ========================================================================================
# CHARTS
# ========================================================================================
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

INPUT_FILE  = "results/cc_event_log.csv"
OUTPUT_HTML = "results/resource_2h_utilization.html"
BASE_DATETIME = pd.Timestamp("2025-01-01 03:00:00")
SIM_DURATION = 50_000

# DEFAULT_CAPACITIES = {
#     "Enfermeiro": 3, "Farmacia": 2, "Tec_Enfermagem": 11, "Eq_Assistencial_CTI": 1,
#     "Eq_Medica": 6, "Anestesista": 6, "Tec_Radiologia": 2, "Eq_Radiologia": 4,
#     "Func_CME": 2, "Eq_Higienizacao": 2
# }

# RESOURCE_SCHEDULE = {
#     "Eq_Medica": [
#         (0, 2, 4), (2, 4, 4), (4, 6, 6), (6, 8, 6), (8, 10, 6), (10, 12, 6),
#         (12, 14, 6), (14, 16, 6), (16, 18, 6), (18, 20, 4), (20, 22, 4), (22, 24, 4)
#     ],
#     "Enfermeiro": [(0, 6, 1), (6, 18, 2), (18, 24, 2)],
#     "Tec_Enfermagem": [(0, 6, 10), (6, 18, 11), (18, 24, 11)]
# }

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















# ===========================================
# Simulation Kit
# ===========================================
def run_single_replication():
    return main()


def run_replications_cli():
    run_replications()


def run_factorial_cli():
    return factorial_analysis()


def run_visualization_cli(simulation_time=15*DAYS):
    return run_visualization(build_model, simulation_time=simulation_time)
# ===========================================