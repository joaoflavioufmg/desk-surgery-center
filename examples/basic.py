# =====================  A Basic Example ==========================
# Patients arrive at an emmergency department in a hospital. 
# They are evaluated in a triagem system and dispatched to additional
# hospital departments. The conceptual models is presented in README.
# =================================================================

# ==============================================================
# Part 1: Basic simulation model: Nurses on emergency triage (hospital)
# ==============================================================
def build_model(until=None, event_logger=None, verbose=True): 
    
    import random
    from desk.core.simulation_model import SimulationModel
    from desk.core.entity import EventLogger
    from desk.blocks.create_block import CreateBlock
    from desk.blocks.process_block import ProcessBlock
    from desk.blocks.dispose_block import DisposeBlock
    
    # Create model
    model = SimulationModel(verbose=verbose)

    # Add resources
    nurses = model.add_resource("Nurses", capacity=3)

    # Define blocks
    arrivals = CreateBlock(
        "Arrivals", model.env,
        inter_arrival_time=lambda: random.expovariate(1/10),
        entity_prefix="Patient",
        event_logger=event_logger
    )

    triage = ProcessBlock(
        "Triage", model.env,
        resource=nurses,
        delay_time=lambda: random.uniform(5, 10),
        resource_units=1,
        event_logger=event_logger
    )

    discharge = DisposeBlock("Discharge", model.env, event_logger=event_logger)

    # Register blocks
    for block in [arrivals, triage, discharge]:
        model.add_block(block)

    # Connect flow
    arrivals.connect_to(triage)
    triage.connect_to(discharge)
       
    return model
    
    
# Run a simulation replication
def main():
    from desk.core.entity import EventLogger
    
    HOURS = 60  # Time conversion factor (base time: minutes)
    DAYS = 1440
    YEARS = 525600
    
    # Create event logger
    event_logger = EventLogger()
    
    model = build_model(event_logger=event_logger, verbose=False)
    
    model.run_simulation(
        until=8*HOURS,          # 8 hours
        warm_up_period=1*HOURS,  # 1 hour
        seed=123
    )

    # Report results
    from desk.analytics.reporting import SimulationReporter
    reporter = SimulationReporter(model)
    reporter.print_results()
    reporter._print_activity_metrics()
    reporter._print_resource_metrics()
    reporter._print_entity_counts()
    reporter._print_block_statistics()
    
    return model, event_logger

# ... (after) "return model, event_logger"...
# ==============================================================
# Part 2: Additional code: Full simulation (replications framework)
# ==============================================================

# Define simulation function wrapper
def simulation_wrapper(seed=None, until=None, warm_up_period=None):
    """Wrapper function for replication framework."""
    
    from desk.core.entity import EventLogger
    event_logger = EventLogger()

    # Create a fresh model
    model = build_model(until=until, event_logger=event_logger, verbose=False)
    
    model.run_simulation(
        validate_resources=False,
        until=until,
        seed=seed,
        warm_up_period=warm_up_period
    )
    
    return model

def run_replications():
    from desk.stats.replication import ReplicationFramework
    
    replication_framework = ReplicationFramework(
        simulation_function=simulation_wrapper,
        n_replications=30
    )

    HOURS = 60  # Time conversion factor (base time: minutes)
    DAYS = 1440
    YEARS = 525600
    
    replication_framework.run_replications(
        base_seed=12345,
        until=8*HOURS,
        warm_up_period=1*HOURS
    )

    # Access results
    df = replication_framework.get_results_dataframe()
    print(df.describe())
   
# ... after "print(df.describe())"...
# ==============================================================
# Part 3: Additional code: Factorial experiment
# ==============================================================
def factorial_analysis():
    """Factorial analysis with simulation."""
    
    from desk.stats.factorial import FactorialExperiment

    HOURS = 60  # Time conversion factor (base time: minutes)
    DAYS = 1440
    YEARS = 525600
    

    def simulation_wrapper(arrival_rate=1, num_nurses=1,
                                seed=None, until=None, warm_up_period=0, **kwargs):
        """Wrapper that adapts parameters for factorial analysis."""

        from desk.core.entity import EventLogger
        event_logger = EventLogger()

        # Create a fresh model
        model = build_model(until=until, event_logger=event_logger, verbose=False)
        
        model.run_simulation(
            validate_resources=False,
            until=until,
            seed=seed,
            warm_up_period=warm_up_period
        )
        
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
        description='Inter arrival rates (min)'
    )
    
    factorial.add_factor(
        factor_name='num_nurses',
        parameter_path='Resource.nurses.capacity',
        levels=[1, 2, 3],
        description='Number of nurses'
    )    
    
    # Run experiment
    factorial.run_factorial_experiment(
        n_replications=5,
        simulation_time=4*HOURS,  # 4 hours
        warm_up_period=1/2*HOURS,    # 1/2 hour
        verbose=True
    )
    
    # Analyze results
    factorial.print_summary()
    factorial.plot_correlation_matrix()
    factorial.plot_main_effects('system_time_avg')
    factorial.plot_interaction_effects('system_time_avg', 'arrival_rate', 'num_nurses')
     
    return factorial

# ... after "return factorial"...
# ==============================================================
# Part 4: Additional code: Interface - visualization
# ==============================================================
from desk.visualization.interface import run_visualization

# ... keep the original (Simulation Kit) code
# ===========================================
# Simulation Kit
# ===========================================

# Run a simulation replication
def run_single_replication():
    return main()

# Run a full simulation    
def run_replications_cli():
    run_replications()

# Run a factorial analysis
def run_factorial_cli():
    return factorial_analysis()

# Run the simulation with interface 
def run_visualization_cli(simulation_time=500):
    return run_visualization(build_model, simulation_time=simulation_time)
# ===========================================