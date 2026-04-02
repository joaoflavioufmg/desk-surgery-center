# =====================================================================
# FILE: 2.py
# =====================================================================
import random
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


# ####################################################################################
# Projeto: Problema do bar
# Autor: João Flávio F. ALmeida <joao.flavio@dep.ufmg.br>
# Descrição: Num bar, os clientes chegam da rua para tomar chope, numa quantidade 
# que varia aleatoriamente em função da sede de cada um. Os intervalos entre chegadas 
# consecutivas são exponencialmente distribuídos com média de 10 minutos. 
# A quantidade de copos que cada cliente toma é definida quando da sua chegada, 
# através do atributo SEDE. A SEDE de um cliente varia de acordo com uma distribuição 
# uniforme discreta com um mínimo de 1 e um máximo de 4 copos. 
# Chegando ao bar, um cliente aguardará sua vez de ser servido. Uma vez servido, 
# atividade cuja duração segue uma distribuição normal com média de 6 segundos e 
# desvio padrão de 1 segundo, o cliente beberá seu copo a seguir. 
# O tempo para beber um copo distribui-se uniformemente com valores entre 5 e 8 minutos. 
# Este ciclo irá se repetir até que o cliente tenha sua sede saciada. 
# Um garçom é responsável pelo atendimento dos clientes e pela lavagem dos copos usados. 
# O atendimento, além do cliente, exige também que um copo limpo esteja disponível. 
# A lavagem dos copos tem duração que pode ser considerada constante e igual a 30 segundos. 
# Supõe-se ainda que o bar dispõe de 70 copos. 
# Pede-se desenvolver um modelo utilizando o DCA para representação do sistema.
# ####################################################################################

# ================================================================
# Each ACD model is implemented here
# ================================================================
def build_model(final_simulation_time=None, event_logger=None, verbose=True,
                        entity_filter=None, resource_filter=None,
                        event_type_filter=None, time_range=None):  
    """Build a simulation model with refactored structure.
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

    if final_simulation_time is None:
        final_simulation_time = 365 * DAYS  # Set default to match the intended simulation time
    
    model = SimulationModel(verbose=verbose,
        entity_filter=entity_filter,
        resource_filter=resource_filter,
        event_type_filter=event_type_filter,
        time_range=time_range)  # NEW: Pass verbose flag

    # Unidade básica para todos os tempos: minutos
    def distribution(tipo):
        taxa_chegadas = 0.1         # por minuto        
        return {
            'chegada': random.expovariate(taxa_chegadas),
            'servir': random.gauss(6, 1),
            'lavar': 0.5,
            'beber': random.uniform(5, 8)
        }.get(tipo,0.0)

    
    # Resources - all priority-based
    garcons = model.add_resource("Garcons", 2, "regular") 
    copos = model.add_resource("Copos", 70, "regular")  
    
    
    # Create blocks
    chegadas_clientes = CreateBlock(
        "ChegadasClientes", model.env,
        inter_arrival_time=lambda: distribution('chegada'),
        entity_prefix="Cliente",
        max_arrivals=None, # Infinito
        first_creation=0.0,
        # priority_generator=prio("Cliente"),
        event_logger=event_logger
    )    
    # CONFIGURE ENTITY ATTRIBUTES # Assign "sede" to each patient
    chegadas_clientes.assign_attributes(
        sede=lambda: random.randint(1, 4)  # Sede entre 1 e 4        
        # sedeOriginal=0
    )

    chegadas_garcons = CreateBlock(
        "ChegadasGarcons", model.env,
        inter_arrival_time=lambda: distribution('chegada'),
        entity_prefix="Garcom",
        max_arrivals=1, 
        first_creation=0.0,
        # priority_generator=prio("Cliente"),
        event_logger=event_logger
    ) 

    decide_ent_origem = DecideBlock(
        "Decide1", model.env,
        decision_type="condition",
        event_logger=event_logger
    )   

    # Define activity priorities
    PRIO_ATIVIDADE = {
        "servir": 0,  # Highest priority
        "lavar": 1    # Lower priority
    }    
    
    servir = MultiProcessBlock(
        "Servir", model.env,
        resource_requirements={
            garcons: 1,
            copos: 1
        },
        delay_time=lambda: distribution('servir'),
        event_logger=event_logger
    )
    servir.set_resource_names({
        garcons: 'Garcons',
        copos: 'Copos'
    })
    servir.set_activity_priority(PRIO_ATIVIDADE["servir"])  # Set activity priority
    
    beber = ProcessBlock(
        "Beber", model.env,
        # resource=None,    # None, se apenas Delay (sem recursos)
        resource=copos,
        delay_time=lambda: distribution('beber'),
        resource_units=1,         # 1 CHECK! 
        event_logger=event_logger
    )
    beber.set_resource_name('Copos')
    # NEW: Configure dynamic attribute modification
    beber.modify_attributes(
        # sedeOriginal=lambda sede: sede,        
        # sede=lambda current: current - 1  # Decrement sede by 1
        sede=lambda current: max(0, current - 1)
    )


    # Lavar activity with lower priority
    lavar = MultiProcessBlock(
        "Lavar", model.env,
        resource_requirements={
            garcons: 1,
            copos: 1
        },
        delay_time=lambda: distribution('lavar'),
        event_logger=event_logger
    )
    lavar.set_resource_names({
        garcons: 'Garcons',
        copos: 'Copos'
    })
    lavar.set_activity_priority(PRIO_ATIVIDADE["lavar"])  # Set activity priority

    decide_satisfeito = DecideBlock(
        "Decide2", model.env,
        decision_type="condition",
        event_logger=event_logger
    )    
    
    dispose = DisposeBlock(
        "Dispose", 
        model.env, 
        event_logger=event_logger)

    decision_time = DecideBlock(
        "DisposeDecision", model.env,
        decision_type="time_condition",
        event_logger=event_logger
    )

    # Add blocks to model
    for block in [chegadas_clientes, chegadas_garcons, servir, 
                beber, decide_satisfeito, decide_ent_origem, 
                decision_time, lavar, dispose]:
        model.add_block(block)
    
    # Connect flow
    chegadas_clientes.connect_to(servir)    
    servir.connect_to(decide_ent_origem)    
    beber.connect_to(decide_satisfeito)

    
    chegadas_garcons.connect_to(lavar)
    lavar.connect_to(decision_time)
    

    # Decision routing functions
    def ori_cliente(entity):
        return "cliente" in entity.id.lower()

    def ori_garcom(entity):
        return "garcom" in entity.id.lower()

    def satisfeito(entity):
        return entity.get_attribute("sede", 0) < 1
        # sede_value = entity.get_attribute("sede", 0)
        # print(f"[DEBUG SATISFEITO] {entity.id}: sede={sede_value}, satisfeito={sede_value < 1}")
        # return sede_value < 1
    
    def nao_satisfeito(entity):
        return entity.get_attribute("sede", 0) >= 1
        # sede_value = entity.get_attribute("sede", 0)
        # print(f"[DEBUG NAO_SATISFEITO] {entity.id}: sede={sede_value}, nao_satisfeito={sede_value >= 1}")
        # return sede_value >= 1
    
    # Add decision routes
    decide_ent_origem.add_route("Cliente", beber, condition=ori_cliente)
    decide_ent_origem.add_route("Garcom", lavar, condition=ori_garcom)

    decide_satisfeito.add_route("Satisfeito", dispose, condition=satisfeito)    
    decide_satisfeito.add_route("Beber_mais", servir, condition=nao_satisfeito)

    decision_time.add_route("Dispose_Yes", dispose,
        time_condition=lambda t: t >= (final_simulation_time - 10))
    decision_time.add_route("Dispose_No", lavar,
        time_condition=lambda t: t < (final_simulation_time - 10))
    
   

    # ================================================================
    # CONFIGURE FINANCIAL ATTRIBUTES
    # ================================================================    
    # Assign costs to each activity
    servir.assign_attributes(cost=lambda: random.uniform(20, 30))    
    lavar.assign_attributes(cost=lambda: random.uniform(10, 20))
    dispose.assign_attributes(revenue=lambda: random.uniform(50, 100))    
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
        duration=24*HOURS,
        warm_up_period=2*HOURS,        
        seed=123,
        check_stability=True
    )

    model = build_model(config.duration, event_logger, verbose=False)

    
    
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
        until=24*60,
        warm_up_period=2*60
    )

    # Access results
    df = replication_framework.get_results_dataframe()
    print(df.describe())
# ================================================================
    

# ================================================================
# Factorial Analysis
# ================================================================
def factorial_analysis():
    """Factorial analysis."""

    HOURS = 60  # Time conversion factor (base time: minutes)
    DAYS = 1440
    YEARS = 525600

    # Create configuration
    config = SimulationConfig(
        duration=24*HOURS,
        warm_up_period=2*HOURS,        
        seed=123,
        check_stability=True        
    )
    
    # Define simulation function wrapper
    def simulation_wrapper(arrival_rate=10, num_garcons=1, num_copos=70,
                                    seed=None, until=None, warm_up_period=0, **kwargs):
        """Wrapper that adapts parameters for factorial analysis."""

        # ############################################################
        # # O modelo de simulação é importado aqui
        # ############################################################
        
        # This would need to be modified in your actual model to accept these parameters
        # For now, this is a template showing how to structure it
        model = build_model(config.duration,  verbose=False)
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
        levels=[10, 15, 20],  # Minutes between arrivals
        description='Taxa de chegada de clientes (min)'
    )
    
    factorial.add_factor(
        factor_name='num_garcons',
        parameter_path='Resource.garcons.capacity',
        levels=[1, 2, 3],
        description='Número de garçons'
    )
    
    factorial.add_factor(
        factor_name='num_copos',
        parameter_path='Resource.copos.capacity',
        levels=[70, 80, 90],
        description='Número de copos'
    )
    
    # Run experiment
    factorial.run_factorial_experiment(
        n_replications=5,
        simulation_time=40*60,  # 40 hours
        warm_up_period=7*60,    # 7 hours
        verbose=True
        # verbose=False
    )
    
    # Analyze results
    factorial.print_summary()
    factorial.plot_correlation_matrix()
    factorial.plot_main_effects('system_time_avg')
    factorial.plot_interaction_effects('system_time_avg', 'arrival_rate', 'num_garcons')
    
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
    
    HOURS = 60  # Time conversion factor (base time: Minutos)
    DAYS = 1440
    YEARS = 525600
    
    # Create configuration
    config = SimulationConfig(
        duration=30,
        warm_up_period=5,
        # duration=8*HOURS,
        # warm_up_period=0.5*HOURS,
        # duration=21*DAYS,
        # warm_up_period=5*DAYS,        
        seed=123,
        check_stability=True
    )
    config.validate()

    # Create event logger
    event_logger = EventLogger()
    
    # Build model
    print("Building ex2 model...")
    verbose = config.duration <= 2*HOURS
    model = build_model(config.duration, event_logger, verbose=verbose)
    
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
    
    pause_simulation()
    
    # === ANALYSIS PHASE (using separate modules) ===

    # ========================================
    # Trace specific patient
    # ========================================    
    print("\n" + "="*80)
    print("FILTER: Journey of Cliente_1")
    print("="*80)    
    pause_simulation()
    model.trace_entity('Cliente_1')        
    
    # ========================================
    # Replay with filters
    # ========================================
    print("\n" + "="*80)
    print("FILTER: Replay - First 3 customers only")
    print("="*80)    
    pause_simulation()
    model.replay_trace(entity_pattern = r'^Cliente_[1-3]$')    

    # ========================================
    # Trace specific resource
    # ========================================
    print("\n" + "="*80)
    print("FILTER: Replay - Garcons interactions only")
    print("="*80)    
    pause_simulation()
    model.replay_trace(resource_filter={'Garcons'})    

    # ========================================
    # Trace specific event types
    # ========================================
    print("\n" + "="*80)
    print("FILTER: Replay - Queue and service events only")
    print("="*80)    
    pause_simulation()
    model.replay_trace(event_type_filter={'queue', 'service_start', 'service_end'})    

    # ========================================
    # Trace time window
    # ========================================
    print("\n" + "="*80)
    print("FILTER: Replay - Events between t=20 and t=40")
    print("="*80)    
    pause_simulation()
    model.replay_trace(time_range=(20, 40))    

    # ========================================
    # Combined filters
    # ========================================
    print("\n" + "="*80)
    print("FILTER: Replay - Cliente_1 at garcons (queue + service)")
    print("="*80)    
    pause_simulation()
    model.replay_trace(
        entity_filter={'Cliente_1'},
        resource_filter={'Garcons'},
        event_type_filter={'queue', 'service_start', 'service_end'}
    )    

    # ========================================
    # Multiple customers journeys
    # ========================================
    print("\n" + "="*80)
    print("FILTER: Detailed journeys of first 3 customers")
    print("="*80)    
    pause_simulation()
    model.trace_entities(['Cliente_1', 'Cliente_2', 'Cliente_3'])    

    # ========================================
    # Trace statistics
    # ========================================
    model.print_trace_statistics()
    pause_simulation()
    
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
    plotter.plot_resource_use_over_time(show_warm_up=True, resource='Garcons', moving_average_window=50)
    plotter.plot_resource_use_over_time(show_warm_up=True, resource='Copos', moving_average_window=50)    
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
    df = event_logger.export_to_csv("results/ex2_event_log.csv")
    print(f"\nFirst 10 events:")
    print(df.head(10))
    
    # 6. Direct metrics access (if needed)
    metrics = MetricsCollector(model)
    entity_metrics = metrics.get_entity_metrics_summary()
    resource_metrics = metrics.get_resource_metrics_summary()
    
    print(f"\nAverage system time: {entity_metrics['tempo_medio_sistema']:.2f} min")
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


def run_visualization_cli(simulation_time=8*60):
    return run_visualization(build_model, simulation_time=simulation_time)
# ===========================================