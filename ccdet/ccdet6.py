# =====================================================================
# FILE: hrtn.py
# =====================================================================
import random
import math
import sys
from desk.stats.factorial import FactorialExperiment
from desk.stats.replication import ReplicationFramework    
from desk.analytics.financial import FinancialAnalyzer
from desk.validation.resource_validator import ResourceValidator
from desk.core.simulation_model import SimulationModel
from desk.core.entity import EventLogger
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
# desk-sim -m ccdet/ccdet6.py --mode visualization
# desk-sim -m ccdet/ccdet6.py --mode single
# desk-sim -m ccdet/ccdet6.py --mode replications
# desk-sim -m ccdet/ccdet6.py --mode factorial

# ================================================================
# Desk-sim: DIST-FIT Which is the best data distribution?
# ================================================================
# desk-distfit -d ccdet/input_data/1_int_cheg.txt
# desk-distfit -d ccdet/input_data/2_adm_conf.txt
# desk-distfit -d ccdet/input_data/3_ato_anestetico.txt
# desk-distfit -d ccdet/input_data/cir_p.txt
# desk-distfit -d ccdet/input_data/cir_m.txt
# desk-distfit -d ccdet/input_data/cir_g.txt
# desk-distfit -d ccdet/input_data/3_pos_cir.txt

# ================================================================
HOURS = 60  # Time conversion factor (base time: Minutos)
DAYS = 1440
YEARS = 525600
# ================================================================

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

    def make_time_dependent_arrival(base_dist, arrival_slots, env=model.env, num_sources=1):
        """
        Returns a zero-argument callable that yields a time-scaled inter-arrival time.

        Works with ANY base distribution or scalar — no knowledge of the
        distribution family is required.  The scaling is applied directly in
        real (time) space:

            inter_arrival = base_sample / k

        where k = slot_fraction * num_slots is the relative intensity of the
        current 2-hour window vs. a flat (uniform) baseline.

            k > 1  →  busier slot  →  shorter inter-arrivals  (divide shrinks the value)
            k < 1  →  quieter slot →  longer  inter-arrivals  (divide enlarges the value)
            k = 1  →  average slot →  base sample unchanged

        This is mathematically equivalent to the distribution-specific tricks:
        • Exponential:  dividing the sample = multiplying the rate  (1/k·mean → rate·k)
        • Lognormal:    dividing the sample = shifting mu by −log(k) in log-space
        • Any other:    scales the mean by 1/k while preserving the CV (shape)

        Parameters
        ----------
        base_dist : callable or numeric
            The base inter-arrival distribution, one of:
            - Zero-argument callable returning a positive number:
                lambda: random.expovariate(1/53)
                lambda: random.lognormvariate(4.0292, 1.2374)
                lambda: random.triangular(40, 53, 70)
                lambda: random.gammavariate(2.0, 26.5)
            - A numeric scalar (constant inter-arrival):
                53
        arrival_slots : list of (start_h, end_h, fraction) tuples
            Empirical 2-hour slot fractions; fractions must sum to 1.0.
            Each tuple: (hour_start, hour_end, fraction_of_daily_volume)
        env : simpy.Environment
            Simulation environment — used to read model.env.now.
        days : int, optional
            Minutes per simulated day (default 1440).

        Returns
        -------
        callable
            A zero-argument function compatible with DESK's inter_arrival_time=.

        Examples
        --------
        # Lognormal base distribution
        arrivals_cc = CreateBlock(
            "Cheg_CC", model.env,
            inter_arrival_time=make_time_dependent_arrival(
                base_dist=lambda: random.lognormvariate(4.0292, 1.2374),
                arrival_slots=ARRIVAL_SLOTS,
                env=model.env,
            ), ...
        )

        # Exponential base distribution
        arrivals_cc = CreateBlock(
            "Cheg_CC", model.env,
            inter_arrival_time=make_time_dependent_arrival(
                base_dist=lambda: random.expovariate(1/53),
                arrival_slots=ARRIVAL_SLOTS,
                env=model.env,
            ), ...
        )

        # Constant (scalar) inter-arrival
        arrivals_cc = CreateBlock(
            "Cheg_CC", model.env,
            inter_arrival_time=make_time_dependent_arrival(
                base_dist=53,
                arrival_slots=ARRIVAL_SLOTS,
                env=model.env,
            ), ...
        )
        """
        DAYS = 1440
        num_slots = len(arrival_slots)

        def _sample_base():
            """Draw one sample from the base distribution (or return the scalar)."""
            return base_dist() if callable(base_dist) else float(base_dist)

        def time_dependent_arrival():
            # ── 1. Locate the current 2-hour slot ─────────────────────────────
            current_hour = (env.now % DAYS) / 60.0

            slot_fraction = arrival_slots[-1][2]          # fallback: last slot
            for start_h, end_h, fraction in arrival_slots:
                if start_h <= current_hour < end_h:
                    slot_fraction = fraction
                    break

            # ── 2. Compute relative intensity vs. flat baseline ────────────────
            # If all slots were equal each would carry 1/num_slots of daily volume.
            # k is how many times busier this slot is than that baseline.
            k = slot_fraction * num_slots                 # k ∈ (0, num_slots]

            # ── 3. Sample and scale ────────────────────────────────────────────
            # Dividing by k is the only operation needed — no distribution-specific
            # parameter manipulation required.
            return (_sample_base()/num_sources) / k

        return time_dependent_arrival


    # Unidade básica para todos os tempos: minutos
    def distribution(tipo):
        # Arrival rates (per day → per minute if DAYS = 1440)
        # arrival_rate_cc  = 1/53 # per minute        

        distributions = {            
            # Arrivals            
            #'arrival_cc': random.expovariate(arrival_rate_cc),
                        
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
            # '4_monit_permanencia_alta_srpa': random.triangular(480, 1680, 2880),
            '4_monit_permanencia_alta_srpa': random.triangular(240, 840, 1440),            

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


    # ---------------------------------------------------------------
    # Time-varying resource staffing schedule
    # Each resource maps to a list of (start_h, end_h, capacity).
    # Resources NOT listed here keep their default capacity unchanged.
    # ---------------------------------------------------------------
    RESOURCE_SCHEDULE = {
        "Eq_Medica": [
            ( 0,  2, 6),
            ( 2,  4, 6),   # quiet night → reduced staff
            ( 4,  6, 6),
            ( 6,  8, 6),
            ( 8, 10, 6),
            (10, 12, 6),   # peak → full team
            (12, 14, 6),
            (14, 16, 6),
            (16, 18, 6),
            (18, 20, 6),
            (20, 22, 6),
            (22, 24, 6),
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
    
    
    # ============================ ACTIVITIES ====================
    # Create block
    arrivals_cc = CreateBlock(
        "Cheg_CC", model.env,
        # inter_arrival_time=lambda: random.expovariate(1/4),
        # inter_arrival_time=lambda: distribution('arrival_cc'),
        inter_arrival_time=make_time_dependent_arrival(
            # base_dist=lambda: 1 + 388.059 * random.betavariate(0.945526, 4.24463),  # ← time-dependent
            base_dist=lambda: 1926/1292 * (1 + 6292.79 * random.betavariate(0.835686, 49.5466)),  # ← time-dependent
            arrival_slots=ARRIVAL_SLOTS,
            num_sources=5),          # ← 5 parallel CreateBlocks),
        entity_prefix="CC_Patient",
        max_arrivals=None, # Infinito
        first_creation=0.0,
        # priority_generator=patient_severity,
        event_logger=event_logger
    )         

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
    # admission_decision = DecideBlock(
    #     "Origem", model.env,
    #     decision_type="probability",
    #     event_logger=event_logger
    # )

    # discharge_decision = DecideBlock(
    #     "Encaminha", model.env,
    #     decision_type="probability",
    #     event_logger=event_logger
    # )

    origem_paciente_decision = DecideBlock(
        "Origem_Paciente", model.env,
        decision_type="probability",
        event_logger=event_logger
    )

    porte_cirurgia_decision = DecideBlock(
        "Porte_Cir", model.env,
        decision_type="probability",
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
    discharge_srpa = DisposeBlock("Saida_SRPA", model.env, event_logger=event_logger)     
    # ============================================================


    # ============================ INCLUDE ALL BLOCKS ====================    
    # Add blocks to model
    for block in [arrivals_cc, prep_sala_P16, prep_sala_P2, prep_sala_P3a9,
                  origem_paciente_decision, 
                  adm_conf_paciente_P11a, adm_conf_paciente_P11b, 
                  adm_conf_paciente_P12a15, adm_paciente_P1617, 
                  proc_cirurgico_P18, proc_cirurgico_P19, 
                  porte_cirurgia_decision,
                  faz_ex_radio_cir_p_decision, faz_ex_radio_cir_m_decision, faz_ex_radio_cir_g_decision,
                  proc_cirurgico_P_P20_025, proc_cirurgico_P_P20aP22_015, proc_cirurgico_P_P20aP22_015_Radio, proc_cirurgico_P_P20_060, 
                  proc_cirurgico_M_P20_025, proc_cirurgico_M_P20aP22_015, proc_cirurgico_M_P20aP22_015_Radio, proc_cirurgico_M_P20_060, 
                  proc_cirurgico_G_P20_025, proc_cirurgico_G_P20aP22_015, proc_cirurgico_G_P20aP22_015_Radio, proc_cirurgico_G_P20_060,
                  proc_cirurgico_pos_P23aP30,
                  limpeza_organizacao_P37, limpeza_organizacao_P38, limpeza_organizacao_P39,
                  discharge_srpa
                  ]:
        model.add_block(block)
    # ====================================================================
    
    # ============================ CONNECT ALL BLOCKS ====================    
    arrivals_cc.connect_to(prep_sala_P16)
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

    porte_cirurgia_decision.add_route("Cir Pequeno", proc_cirurgico_P_P20_025, probability=0.4)
    porte_cirurgia_decision.add_route("Cir Medio", proc_cirurgico_M_P20_025, probability=0.4)
    porte_cirurgia_decision.add_route("Cir Grande", proc_cirurgico_G_P20_025, probability=0.2)

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
    limpeza_organizacao_P39.connect_to(discharge_srpa)

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
    
    
    # === ANALYSIS PHASE (using separate modules) ===
    #     
    # ========================================
    # Trace specific patient
    # ========================================    
    print("\n" + "="*80)
    print("FILTER: Journey of CC_Patient_1")
    print("="*80)    
    pause_simulation()
    model.trace_entity('CC_Patient_1')        
    
    # # ========================================
    # # Replay with filters
    # # ========================================
    # print("\n" + "="*80)
    # print("FILTER: Replay - First 3 patients only")
    # print("="*80)    
    # pause_simulation()
    # model.replay_trace(entity_pattern = r'^Patient_[1-3]$')
    
    # ========================================
    # Trace specific resource
    # ========================================
    print("\n" + "="*80)
    print("FILTER: Replay - CC Tec_Enfermagem interactions only")
    print("="*80)    
    pause_simulation()
    model.replay_trace(resource_filter={'Tec_Enfermagem'})
    
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
    plotter.plot_wip_over_time()
    plotter.plot_system_time_distribution()

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
    df = event_logger.export_to_csv("results/ccdet_event_log.csv")
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