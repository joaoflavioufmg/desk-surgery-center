# =====================================================================
# FILE: hospital.py
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
    
    model = SimulationModel(verbose=verbose,
        entity_filter=entity_filter,
        resource_filter=resource_filter,
        event_type_filter=event_type_filter,
        time_range=time_range)  # NEW: Pass verbose flag

    # Unidade básica para todos os tempos: minutos
    def distribution(tipo):
        taxa_chegadas=4         # por minuto        
        return {
            'arrival': random.expovariate(1/taxa_chegadas),
            'triage': random.uniform(2, 3),
            'consultation': random.uniform(5, 15),
            'pharmacy': random.expovariate(1/5)
        }.get(tipo,0.0)

    
    # Resources - all priority-based
    nursesT = model.add_resource("nursesT", 2, "priority") # << To Validade!
    nurses = model.add_resource("nurses", 3, "priority")
    doctors = model.add_resource("doctors", 4, "priority")
    # pharmacy = model.add_resource("pharmacy", 4, "preemptive")
    pharmacy = model.add_resource("pharmacy", 4, "priority")
    
    # Patient severity generator
    def patient_severity():
        severity_dist = [0.1, 0.2, 0.3, 0.3, 0.1]
        return random.choices([0, 1, 2, 3, 4], weights=severity_dist)[0]
    
    # Create blocks
    arrivals = CreateBlock(
        "Arrivals", model.env,
        # inter_arrival_time=lambda: random.expovariate(1/4),
        inter_arrival_time=lambda: distribution('arrival'),
        entity_prefix="Patient",
        max_arrivals=None, # Infinito
        first_creation=0.0,
        priority_generator=patient_severity,
        event_logger=event_logger
    )
    
    triage = ProcessBlock(
        "Triage", model.env,
        # resource=None,    # None, se apenas Delay (sem recursos)
        resource=nursesT,
        # delay_time=lambda: random.uniform(2, 5),
        delay_time=lambda: distribution('triage'),
        resource_units=2,         # 2 CHECK! nurse of triage per service
        event_logger=event_logger
    )
    triage.set_resource_name('nursesT')

    
    consultation = MultiProcessBlock(
        "Consultation", model.env,
        resource_requirements={
            doctors: 1,
            nurses: 1
            # pharmacy: 1
        },
        # delay_time=lambda: random.uniform(5, 15),
        delay_time=lambda: distribution('consultation'),
        event_logger=event_logger
    )
    consultation.set_resource_names({
        doctors: 'doctors',
        nurses: 'nurses'
        # pharmacy: 'pharmacy'
    })
    
    treatment_decision = DecideBlock(
        "Treatment_Decision", model.env,
        decision_type="condition",
        event_logger=event_logger
    )
    
    moderate_treatment = DecideBlock(
        "Moderate_Treatment", model.env,
        decision_type="probability",
        event_logger=event_logger
    )

    minor_treatment = DecideBlock(
        "Minor_Treatment", model.env,
        decision_type="probability",
        event_logger=event_logger
    )

    pharmacy_block = ProcessBlock(
        "Pharmacy", model.env,
        resource=pharmacy,
        # delay_time=lambda: random.expovariate(1/5),
        delay_time=lambda: distribution('pharmacy'),
        resource_units=2,                 # 2 pharmacists per service
        event_logger=event_logger
    )
    pharmacy_block.set_resource_name('pharmacy')
    
    need_medication = DecideBlock(
        "Need_medication", model.env,
        decision_type="probability",
        event_logger=event_logger
    )
    
    
    discharge = DisposeBlock("Discharge", model.env, event_logger=event_logger)
    

    # Add blocks to model
    for block in [arrivals, triage, consultation, treatment_decision,
                  pharmacy_block, moderate_treatment, minor_treatment, 
                  need_medication, discharge]:
        model.add_block(block)
    
    
    # Connect flow
    arrivals.connect_to(triage)
    triage.connect_to(treatment_decision)

    # Decision routing functions
    def needs_intensive_treatment(entity):
        return entity.priority <= 1
    
    def needs_moderate_treatment(entity):
        return entity.priority == 2 # and random.random() < 0.80
    
    def needs_minor_treatment(entity):
        return entity.priority == 3 # and random.random() < 0.90
    
    def needs_only_medication(entity):
        return not (needs_intensive_treatment(entity) or
                   needs_moderate_treatment(entity) or
                   needs_minor_treatment(entity))
    
    # Add decision routes
    treatment_decision.add_route("Critical_Emergency", consultation,
                                condition=needs_intensive_treatment)
    treatment_decision.add_route("Urgent", moderate_treatment,
                                condition=needs_moderate_treatment)
    treatment_decision.add_route("Semi_Urgent", minor_treatment,
                                condition=needs_minor_treatment)
    treatment_decision.add_route("Non_Urgent", pharmacy_block,
                                condition=needs_only_medication)
    
    moderate_treatment.add_route("Urgent", consultation, probability=0.8)
    # Importante! Para contabilizar as saídas e o WIP
    moderate_treatment.add_route("No_Consult", discharge, probability=0.2)

    minor_treatment.add_route("Semi_Urgent", consultation, probability=0.9)
    # Importante! Para contabilizar as saídas e o WIP
    minor_treatment.add_route("No_Consult", discharge, probability=0.1)
    
    consultation.connect_to(need_medication)

    need_medication.add_route("Needs_Medication", pharmacy_block, probability=0.9)
    need_medication.add_route("Direct_Discharge", discharge, probability=0.1)
    
    pharmacy_block.connect_to(discharge)


    # ================================================================
    # CONFIGURE FINANCIAL ATTRIBUTES
    # ================================================================    
    # Assign costs to each activity
    triage.assign_attributes(
        cost=lambda: random.uniform(20, 30)  # Triage costs $20-30
    )
    
    consultation.assign_attributes(
        cost=lambda: random.uniform(100, 200)  # Consultation costs $100-200
    )
    
    pharmacy_block.assign_attributes(
        cost=lambda: random.uniform(15, 50)  # Medication costs $15-50
    )
    
    # Assign revenue at discharge (based on patient complexity)
    def calculate_revenue():
        """Revenue varies by patient complexity"""
        return random.uniform(200, 300)
    
    discharge.assign_attributes(revenue=calculate_revenue)    
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

    # model = build_model(event_logger)
    model = build_model(config.duration, event_logger, verbose=False)

    # # Validate once on first run
    # if seed == 12345:
    #     model.validate_resources()
    
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
    """Example of factorial analysis with hospital simulation."""

    HOURS = 60  # Time conversion factor (base time: minutes)
    DAYS = 1440
    YEARS = 525600
    
    # Define simulation function wrapper
    def simulation_wrapper(arrival_rate=4, num_doctors=4, num_nurses=3,
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
        levels=[3, 4, 5],  # Minutes between arrivals
        description='Taxa de chegada de pacientes (min)'
    )
    
    factorial.add_factor(
        factor_name='num_doctors',
        parameter_path='Resource.doctors.capacity',
        levels=[3, 4, 5],
        description='Número de médicos'
    )
    
    factorial.add_factor(
        factor_name='num_nurses',
        parameter_path='Resource.nurses.capacity',
        levels=[2, 3, 4],
        description='Número de enfermeiros'
    )
    
    # Run experiment
    factorial.run_factorial_experiment(
        n_replications=5,
        simulation_time=40*60,  # 40 hours
        warm_up_period=7*60,    # 7 hours
        verbose=True
    )
    
    # Analyze results
    factorial.print_summary()
    factorial.plot_correlation_matrix()
    factorial.plot_main_effects('system_time_avg')
    factorial.plot_interaction_effects('system_time_avg', 'arrival_rate', 'num_doctors')
    
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
    print("Building hospital model...")

    # Create configuration
    config = SimulationConfig(
        # warm_up_period=0
        # until=20
        duration=24*HOURS,
        warm_up_period=2*HOURS,
        # duration=21*DAYS,
        # warm_up_period=5*DAYS,        
        seed=123,
        check_stability=True
    )
    config.validate()
    
    # model = build_model(event_logger)
    model = build_model(config.duration, event_logger, verbose=True)
    
    
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
    print("FILTER: Journey of Patient_1")
    print("="*80)    
    pause_simulation()
    model.trace_entity('Patient_1')        
    
    # ========================================
    # Replay with filters
    # ========================================
    print("\n" + "="*80)
    print("FILTER: Replay - First 3 patients only")
    print("="*80)    
    pause_simulation()
    model.replay_trace(entity_pattern = r'^Patient_[1-3]$')
    
    # ========================================
    # Trace specific resource
    # ========================================
    print("\n" + "="*80)
    print("FILTER: Replay - Doctor interactions only")
    print("="*80)    
    pause_simulation()
    model.replay_trace(resource_filter={'doctors'})
    
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
    print("FILTER: Replay - Patient_1 at doctors (queue + service)")
    print("="*80)    
    pause_simulation()
    model.replay_trace(
        entity_filter={'Patient_1'},
        resource_filter={'doctors'},
        event_type_filter={'queue', 'service_start', 'service_end'}
    )    

    # ========================================
    # Multiple patient journeys
    # ========================================
    print("\n" + "="*80)
    print("FILTER: Detailed journeys of first 3 patients")
    print("="*80)    
    pause_simulation()
    model.trace_entities(['Patient_1', 'Patient_2', 'Patient_3'])
    
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
    plotter.plot_resource_use_over_time(show_warm_up=True, resource='nursesT', moving_average_window=50)
    plotter.plot_resource_use_over_time(show_warm_up=True, resource='nurses', moving_average_window=50)
    plotter.plot_resource_use_over_time(show_warm_up=True, resource='doctors', moving_average_window=50)
    plotter.plot_resource_use_over_time(show_warm_up=True, resource='pharmacy', moving_average_window=50)
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
    df = event_logger.export_to_csv("results/hospital_event_log.csv")
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


def run_visualization_cli(simulation_time=500):
    return run_visualization(build_model, simulation_time=simulation_time)
# ===========================================