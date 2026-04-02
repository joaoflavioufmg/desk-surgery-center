# =====================================================================
# FILE: 3a.py
# =====================================================================
import random
import sys
from desk.stats.factorial import FactorialExperiment
from desk.stats.replication import ReplicationFramework    
from desk.analytics.financial import FinancialAnalyzer
from desk.validation.resource_validator import ResourceValidator
from desk.core.simulation_model import SimulationModel
from desk.core.simulation_observer import SimulationObserver
from desk.core.model_variables import ModelVariableTracker
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
# Projeto: Central telefônica (variante 1)
# Autor: João Flávio F. ALmeida <joao.flavio@dep.ufmg.br>
# Descrição: Considere o exemplo anterior (3) da central telefônica. 
# Suponha que uma chamada possa ser perdida ao encontrar o sistema congestionado 
# (todos os troncos ocupados), fato que ocorre com 30% de probabilidade, 
# ou então, voltar a ser efetivada (retorno) dentro de 10 segundos. 
# Não há limite preestabelecido para o número de retornos que uma chamada pode ter.
# ####################################################################################

# ================================================================
# Each ACD model is implemented here
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

    if final_simulation_time is None:
        final_simulation_time = 365 * DAYS  # Set default to match the intended simulation time
    
    model = SimulationModel(verbose=verbose,
        entity_filter=entity_filter,
        resource_filter=resource_filter,
        event_type_filter=event_type_filter,
        time_range=time_range)  # NEW: Pass verbose flag

    # Unidade básica para todos os tempos: minutos
    def distribution(tipo):
        taxa_chegadas = 15         # 15 por minuto = 1 a cada 4 segundos
        return {
            'chegada': random.expovariate(taxa_chegadas),
            'atendimento': random.expovariate(1/2), # Média 2 minutos
            'espera': 10/60 # 10 segundos
        }.get(tipo,0.0)

    
    # Resources - regular, priority, preempt
    troncos = model.add_resource("Troncos", 30, "regular") 
    
    # # Create tracker
    # variable_tracker = ModelVariableTracker(model)    

    # variable_tracker.add_variable(
    #     'num_chamadas_perdidas',
    #     initial_value=0,
    #     description='Número total de chamadas perdidas',
    #     unit='unidades')

    # variable_tracker.add_variable(
    #     'percentual_chamdas_perdidas',
    #     initial_value=0,
    #     description='Percentual de chamadas perdidas',
    #     unit='%',
    #     calculate_fn=lambda m: (
    #         variable_tracker.get_current('num_chamadas_perdidas') / m.entity_count * 100
    #         if m.entity_count > 0 else 0
    #     ))

    # Add model variables
    model.add_model_variable('num_chamadas_perdidas', 0, 
                            'Número de chamadas perdidas', 'unidades')
    model.add_model_variable('percentual_chamadas_perdidas', 0,
                            'Percentual de chamadas perdidas', '%',
                            calculate_fn=lambda m: (
                                m.variable_tracker.get_current('num_chamadas_perdidas') /
                                max(1, m.entity_count) * 100))
    
    # Create blocks
    chegadas_chamadas = CreateBlock(
        "ChegadasChamadas", model.env,
        inter_arrival_time=lambda: distribution('chegada'),
        entity_prefix="Chamada",
        max_arrivals=None, # Infinito
        first_creation=0.0,
        # priority_generator=prio("Cliente"),
        event_logger=event_logger
    )      

    decide_fila_tronco = DecideBlock(
        "DecideTronco", model.env,
        decision_type="condition_generic",
        event_logger=event_logger
    ) 

    decide_fila_tronco30 = DecideBlock(
        "DecideTronco30", model.env,
        decision_type="probability",
        event_logger=event_logger
    )
    
    atendimento = ProcessBlock(
        "Atendimento", model.env,
        # resource=None,    # None, se apenas Delay (sem recursos)
        resource=troncos,
        delay_time=lambda: distribution('atendimento'),
        resource_units=1,         # 1 CHECK! 
        event_logger=event_logger
    )
    atendimento.set_resource_name('Troncos')    

    espera = ProcessBlock(
        "Espera", model.env,
        resource=None,    # None, se apenas Delay (sem recursos)        
        delay_time=lambda: distribution('espera'),        
        event_logger=event_logger
    ) 
    
    dispose_atendida = DisposeBlock(
        "DisposeAtendida", 
        model.env, 
        event_logger=event_logger)

    dispose_perdida = DisposeBlock(
        "DisposePerdida", 
        model.env, 
        event_logger=event_logger)


    # Add blocks to model
    for block in [chegadas_chamadas, espera, atendimento, 
        decide_fila_tronco, decide_fila_tronco30,
        dispose_atendida, dispose_perdida]:
        model.add_block(block)
    
    # Connect flow
    chegadas_chamadas.connect_to(decide_fila_tronco)    
    atendimento.connect_to(dispose_atendida)
    espera.connect_to(decide_fila_tronco)        
    
    # Add decision routes
    decide_fila_tronco.add_route(
        "Atender", atendimento, 
        condition_generic=lambda e, ctx: (
            ctx['resources']['Troncos'].count < ctx['resources']['Troncos'].capacity
            )
        )
    decide_fila_tronco.add_route(
        "Aguarda", decide_fila_tronco30, 
        condition_generic=lambda e, ctx: (
            ctx['resources']['Troncos'].count >= ctx['resources']['Troncos'].capacity
            )
        )  

    decide_fila_tronco30.add_route("Perdida", dispose_perdida, probability=0.3)
    # Importante! Para contabilizar as saídas e o WIP
    decide_fila_tronco30.add_route("NovaTentativa", espera, probability=0.7) 
    # ================================================================
    # CREATE OBSERVER (separate from blocks)
    # ================================================================    
    observer = SimulationObserver(model)
    
    # DEFINE CALLBACK: What to do when call is lost
    # def count_lost_call(entity, block_name, time, verbose=True):        
    def count_lost_call(entity, block_name, time, verbose=verbose):        
        """Called when entity disposed to DisposePerdida."""
        tracker = model.variable_tracker
        current = tracker.get_current('num_chamadas_perdidas')
        tracker.update('num_chamadas_perdidas', time, current + 1)
        tracker.update('percentual_chamadas_perdidas')  # Auto-calculate
        if verbose:
            print(f"[{time:.2f}] Chamada {entity.id} PERDIDA - Total: {current + 1}")
    
    # ATTACH OBSERVER: Monitor specific dispose block
    observer.on_entity_disposed(
        block_name='DisposePerdida',
        callback=count_lost_call
    )

       
    # ================================================================
    # CONFIGURE FINANCIAL ATTRIBUTES
    # ================================================================    
    # Assign costs to each activity
    atendimento.assign_attributes(cost=lambda: random.uniform(20, 30))    
    dispose_atendida.assign_attributes(revenue=lambda: random.uniform(50, 100))    
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
        duration=20,
        warm_up_period=2,        
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
        until=20,
        warm_up_period=2
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

    # Create configuration
    config = SimulationConfig(
        duration=24*HOURS,
        warm_up_period=2*HOURS,        
        seed=123,
        check_stability=True        
    )
    
    # Define simulation function wrapper
    def simulation_wrapper(arrival_rate=15, num_troncos=30,
                                    seed=None, until=None, warm_up_period=0, **kwargs):
        """Wrapper that adapts parameters for factorial analysis."""

        # ############################################################
        # # O modelo de simulação é importado aqui
        # ############################################################
        
        # This would need to be modified in your actual model to accept these parameters
        # For now, this is a template showing how to structure it
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
        levels=[4/60, 8/60, 16/60],  # Minutes between arrivals
        description='Taxa de chegada de clientes (min)'
    )
    
    factorial.add_factor(
        factor_name='num_troncos',
        parameter_path='Resource.troncos.capacity',
        levels=[30, 31, 32],
        description='Número de troncos'
    )
    
    
    # Run experiment
    factorial.run_factorial_experiment(
        n_replications=5,
        simulation_time=40,  # 40 min
        warm_up_period=7,    # 7 min
        verbose=True
        # verbose=False
    )
    
    # Analyze results
    factorial.print_summary()
    factorial.plot_correlation_matrix()
    factorial.plot_main_effects('system_time_avg')
    factorial.plot_interaction_effects('system_time_avg', 'arrival_rate', 'num_troncos')
    
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
    
    # Create configuration
    config = SimulationConfig(
        warm_up_period=1,
        duration=60,
        # warm_up_period=0.5*HOURS,
        # duration=8*HOURS,        
        # warm_up_period=5*DAYS,        
        # duration=21*DAYS,        
        seed=123,
        check_stability=True
    )
    config.validate()

    # Create event logger
    event_logger = EventLogger()
    
    # Build model
    print("Building ex3 model...")
    verbose = config.duration <= 1/10*HOURS
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
    
    # === ANALYSIS PHASE (using separate modules) ===

    # ========================================
    # Trace specific chamada
    # ========================================    
    print("\n" + "="*80)
    print("FILTER: Journey of Chamada_1")
    print("="*80)    
    pause_simulation()
    model.trace_entity('Chamada_1')    
    
    
    # ========================================
    # Replay with filters
    # ========================================
    print("\n" + "="*80)
    print("FILTER: Replay - First 3 chamadas only")
    print("="*80)    
    pause_simulation()
    model.replay_trace(entity_pattern = r'^Chamada_[1-3]$')
    

    # ========================================
    # Trace specific resource
    # ========================================
    print("\n" + "="*80)
    print("FILTER: Replay - Troncos interactions only")
    print("="*80)    
    pause_simulation()
    model.replay_trace(resource_filter={'Troncos'})
    

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
    print("FILTER: Replay - Events between t=2 and t=3")
    print("="*80)    
    pause_simulation()
    model.replay_trace(time_range=(2, 3))
    

    # ========================================
    # Combined filters
    # ========================================
    print("\n" + "="*80)
    print("FILTER: Replay - Chamada_1 at Troncos (queue + service)")
    print("="*80)    
    pause_simulation()
    model.replay_trace(
        entity_filter={'Chamada_1'},
        resource_filter={'Troncos'},
        event_type_filter={'queue', 'service_start', 'service_end'}
    )
    

    # ========================================
    # Multiple chamadas journeys
    # ========================================
    print("\n" + "="*80)
    print("FILTER: Detailed journeys of first 3 chamadas")
    print("="*80)    
    pause_simulation()
    model.trace_entities(['Chamada_1', 'Chamada_2', 'Chamada_3'])
    

    # ========================================
    # Trace statistics
    # ========================================
    model.print_trace_statistics()
    pause_simulation()


    # ========================================
    # 2. Detailed reporting
    # ========================================
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
    plotter.plot_resource_use_over_time(show_warm_up=True, resource='Troncos', moving_average_window=50)
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

    # Print variable results
    # ================================================================
    tracker = model.variable_tracker
    print(f"\n{'='*60}")
    print(f"RESULTADOS:")
    print(f"Total de chamadas: {model.entity_count}")
    print(f"Chamadas perdidas: {tracker.get_final('num_chamadas_perdidas')}")
    print(f"Percentual perdido: {tracker.get_final('percentual_chamadas_perdidas'):.2f}%")
    print(f"{'='*60}")
    # ================================================================
    
    # Financial analysis
    print("\nPlotting financial analysys...")
    financial_analyzer = FinancialAnalyzer(model)
    financial_analyzer.print_financial_summary()
    financial_analyzer.plot_financial_breakdown()

    # 5. Export event log
    print("\nExporting event log...")
    df = event_logger.export_to_csv("results/ex3a_event_log.csv")
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


def run_visualization_cli(simulation_time=60):
    return run_visualization(build_model, simulation_time=simulation_time)
# ===========================================