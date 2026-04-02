# =====================================================================
# FILE: ex1.py
# =====================================================================
import random
import sys
from desk.stats.factorial import FactorialExperiment
from desk.stats.replication import ReplicationFramework    
from desk.analytics.financial import FinancialAnalyzer
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
# Projeto: Maquinas operando ininterruptamente 
# Autor: João Flávio F. ALmeida <joao.flavio@dep.ufmg.br>
# Descrição: Uma empresa opera três máquinas, em um determinado setor de sua 
# planta industrial. As máquinas trabalham em operação contínua, 
# interrompendo seu funcionamento apenas para manutenção corretiva. 
# O tempo entre falhas é descrito por uma distribuição exponencial 
# com média de 3 dias. A manutenção é feita por uma única equipe e 
# sua duração segue uma distribuição exponencial com média de 1 dia. 
# Deseja-se simular este problema para avaliar o tempo que as 
# máquinas ficam paradas aguardando por manutenção e para estimar 
# a ocupação média da equipe de manutenção. 
# Para tanto, construir o modelo conceitual do sistema usando 
# diagramas de ciclo de atividades.
# ####################################################################################

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

    # Set default to match the intended simulation time
    if final_simulation_time is None:
        final_simulation_time = 365 * DAYS  
    
    model = SimulationModel(verbose=verbose,
        entity_filter=entity_filter,
        resource_filter=resource_filter,
        event_type_filter=event_type_filter,
        time_range=time_range)  # NEW: Pass verbose flag

    def distribution(tipo):        
        return {
            'arrival': 0, 
            'operacao': random.expovariate(1/(3*DAYS)),
            'manutencao': random.expovariate(1/(1*DAYS))
        }.get(tipo,0.0)  


    # Resources
    equipes = model.add_resource("Equipes", 1, "regular")
    
    
     # Create blocks
    arrivals = CreateBlock(
        "Arrivals", model.env,        
        inter_arrival_time=lambda: distribution('arrival'),
        entity_prefix="Maquina",  
        max_arrivals=3,
        first_creation=0.0,
        event_logger=event_logger
    )
    
    operacao = ProcessBlock(
        "Operacao", model.env,
        resource=None, # Apenas DELAY (sem recurso)
        delay_time=lambda: distribution('operacao'),
        event_logger=event_logger
    ) 
    
    manutencao = ProcessBlock(
        "Manutencao", model.env,
        resource=equipes,
        delay_time=lambda: distribution('manutencao'),
        resource_units=1,                 
        event_logger=event_logger
    )
    manutencao.set_resource_name('Equipes')
   
    
    decision_time = DecideBlock(
        "DisposeDecision", model.env,
        decision_type="time_condition",
        event_logger=event_logger
    )


    decision_time.add_route(
        "Dispose_Yes", 
        next_block=None,  # Will be connected later
        time_condition=lambda t: t >= (final_simulation_time - 0.1*final_simulation_time))

    decision_time.add_route(
        "Dispose_No", 
        next_block=None,  # Will be connected later
        time_condition=lambda t: t < (final_simulation_time - 0.1*final_simulation_time))

    dispose = DisposeBlock(
        "Dispose", 
        model.env, 
        event_logger=event_logger)
    
    # Add blocks to model
    for block in [arrivals, operacao, manutencao, decision_time, dispose]:
        model.add_block(block)

    # Connect flow
    arrivals.connect_to(operacao)
    operacao.connect_to(manutencao)    
    manutencao.connect_to(decision_time)
    decision_time.routes["Dispose_No"]["block"] = operacao
    decision_time.routes["Dispose_Yes"]["block"] = dispose
    
    # ================================================================
    # CONFIGURE FINANCIAL ATTRIBUTES
    # ================================================================    
    # Assign costs to each activity
    operacao.assign_attributes(
        cost=lambda: random.uniform(20, 30)  # Operacao costs $20-30
    )
    
    manutencao.assign_attributes(
        cost=lambda: random.uniform(100, 200)  # Manutencao costs $100-200
    )    
    
    # Assign revenue at discharge (based on patient complexity)
    def calculate_revenue():
        """Revenue varies"""
        return random.uniform(200, 300)
    
    operacao.assign_attributes(revenue=calculate_revenue)    
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
        until=365*DAYS,
        warm_up_period=30*DAYS
    )

    # Access results
    df = replication_framework.get_results_dataframe()
    print(df.describe())
# ================================================================


# ================================================================
# Factorial Analysis
# ================================================================
def factorial_analysis():
    """Factorial analysis with simulation."""

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
    
    # Define simulation function wrapper
    def simulation_wrapper(arrival_rate=1, num_equipes=1,
                                seed=None, until=None, warm_up_period=0, **kwargs):
        """Wrapper that adapts parameters for factorial analysis."""

        # ############################################################
        # # O modelo de simulação é importado aqui
        # ############################################################
        model = build_model(config.duration, verbose=False)
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
        levels=[1, 2, 3],  # Minutes between arrivals
        description='Taxa de chegada de maquinas (min)'
    )
    
    factorial.add_factor(
        factor_name='num_equipes',
        parameter_path='Resource.equipes.capacity',
        levels=[1, 2, 3],
        description='Número de equipes de manutenção'
    )
    
    
    # Run experiment
    factorial.run_factorial_experiment(
        n_replications=5,
        simulation_time=30*DAYS,  # 40 hours
        warm_up_period=3*DAYS,    # 7 hours
        verbose=True
    )
    
    # Analyze results
    factorial.print_summary()
    factorial.plot_correlation_matrix()
    factorial.plot_main_effects('system_time_avg')
    factorial.plot_interaction_effects('system_time_avg', 'arrival_rate', 'num_equipes')
    
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
        # duration=24*HOURS,
        # warm_up_period=2*HOURS,
        duration=30*DAYS,
        warm_up_period=3*DAYS,
        # duration=365*DAYS,
        # warm_up_period=30*DAYS,        
        seed=123,
        check_stability=True
    )
    config.validate()

    # Create event logger
    event_logger = EventLogger()
    
    # Build model
    print("Building ex1 model...")  
    verbose = config.duration <= 30*DAYS
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
    # Trace specific maquina
    # ========================================    
    print("\n" + "="*80)
    print("FILTER: Journey of Maquina_1")
    print("="*80)    
    pause_simulation()
    model.trace_entity('Maquina_1')        
    
    # ========================================
    # Replay with filters
    # ========================================
    print("\n" + "="*80)
    print("FILTER: Replay - First 2 maquinas only")
    print("="*80)    
    pause_simulation()
    model.replay_trace(entity_pattern = r'^Maquina_[1-2]$')    

    # ========================================
    # Trace specific resource
    # ========================================
    print("\n" + "="*80)
    print("FILTER: Replay - Equipe interactions only")
    print("="*80)    
    pause_simulation()
    model.replay_trace(resource_filter={'Equipes'})    

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
    model.replay_trace(time_range=(1000, 10000))    

    # ========================================
    # Combined filters
    # ========================================
    print("\n" + "="*80)
    print("FILTER: Replay - Maquina_1 at equipe (queue + service)")
    print("="*80)    
    pause_simulation()
    model.replay_trace(
        entity_filter={'Maquina_1'},
        resource_filter={'Equipes'},
        event_type_filter={'queue', 'service_start', 'service_end'}
    )    

    # ========================================
    # Multiple patient journeys
    # ========================================
    print("\n" + "="*80)
    print("FILTER: Detailed journeys of first 2 maquinas")
    print("="*80)    
    pause_simulation()
    model.trace_entities(['Maquina_1', 'Maquina_2', 'Maquina_3'])    

    # ========================================
    # Trace statistics
    # ========================================
    model.print_trace_statistics()
    pause_simulation()

        
    print("\n" + "="*60)
    # ========================================
    print("SIMULATION COMPLETE - ANALYZING RESULTS")
    # ========================================
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
    plotter.plot_resource_use_over_time(show_warm_up=True, resource='Equipes', moving_average_window=50)    
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
    df = event_logger.export_to_csv("results/ex1_event_log.csv")
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


def run_visualization_cli(simulation_time=365*1440):
    return run_visualization(build_model, simulation_time=simulation_time)
# ===========================================