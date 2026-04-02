# tests/test_statistics/test_factorial.py
import pytest
import simpy
import pandas as pd
from desk.stats.factorial import FactorialExperiment, FactorLevel
from desk.core.simulation_model import SimulationModel
from desk.blocks.create_block import CreateBlock
from desk.blocks.process_block import ProcessBlock
from desk.blocks.dispose_block import DisposeBlock


def configurable_simulation(arrival_rate=5.0, service_capacity=2, 
                           seed=None, until=100, warm_up_period=0, **kwargs):
    """Configurable simulation for factorial experiments."""
    model = SimulationModel()
    
    resource = model.add_resource("service", capacity=service_capacity)
    
    create = CreateBlock(
        "Arrivals",
        model.env,
        inter_arrival_time=lambda: arrival_rate,
        max_arrivals=20
    )
    
    process = ProcessBlock(
        "Service",
        model.env,
        resource=resource,
        delay_time=lambda: 3.0
    )
    
    dispose = DisposeBlock("Exit", model.env)
    
    model.add_block(create)
    model.add_block(process)
    model.add_block(dispose)
    
    model.connect_blocks("Arrivals", "Service")
    model.connect_blocks("Service", "Exit")
    
    model.run_simulation(
        validate_resources=False,
        until=until,
        seed=seed,
        warm_up_period=warm_up_period
    )
    
    return model


class TestFactorLevel:
    """Test FactorLevel dataclass."""
    
    def test_factor_level_creation(self):
        """Test creating a factor level."""
        factor = FactorLevel(
            factor_name="arrival_rate",
            parameter_path="CreateBlock.inter_arrival_time",
            levels=[3.0, 5.0, 7.0],
            description="Patient arrival rate"
        )
        
        assert factor.factor_name == "arrival_rate"
        assert factor.parameter_path == "CreateBlock.inter_arrival_time"
        assert factor.levels == [3.0, 5.0, 7.0]
        assert factor.description == "Patient arrival rate"
    
    def test_factor_level_without_description(self):
        """Test creating factor without description."""
        factor = FactorLevel(
            factor_name="capacity",
            parameter_path="Resource.capacity",
            levels=[1, 2, 3]
        )
        
        assert factor.description == ""


class TestFactorialExperiment:
    """Test FactorialExperiment functionality."""
    
    def test_factorial_initialization(self):
        """Test creating factorial experiment."""
        factorial = FactorialExperiment(
            simulation_function=configurable_simulation,
            base_seed=123
        )
        
        assert factorial.simulation_function == configurable_simulation
        assert factorial.base_seed == 123
        assert factorial.factors == []
        assert factorial.results == []
    
    def test_default_base_seed(self):
        """Test default base seed."""
        factorial = FactorialExperiment(
            simulation_function=configurable_simulation
        )
        
        assert factorial.base_seed == 12345
    
    def test_add_factor(self):
        """Test adding a factor."""
        factorial = FactorialExperiment(
            simulation_function=configurable_simulation
        )
        
        factorial.add_factor(
            factor_name="arrival_rate",
            parameter_path="CreateBlock.inter_arrival_time",
            levels=[3.0, 5.0],
            description="Arrival rate"
        )
        
        assert len(factorial.factors) == 1
        assert factorial.factors[0].factor_name == "arrival_rate"
        assert factorial.factors[0].levels == [3.0, 5.0]
    
    def test_add_multiple_factors(self):
        """Test adding multiple factors."""
        factorial = FactorialExperiment(
            simulation_function=configurable_simulation
        )
        
        factorial.add_factor("arrival_rate", "path1", [3.0, 5.0])
        factorial.add_factor("service_capacity", "path2", [2, 3])
        factorial.add_factor("service_time", "path3", [2.0, 4.0])
        
        assert len(factorial.factors) == 3
    
    def test_run_factorial_experiment_simple(self):
        """Test running a simple 2x2 factorial."""
        factorial = FactorialExperiment(
            simulation_function=configurable_simulation,
            base_seed=123
        )
        
        factorial.add_factor(
            "arrival_rate",
            "CreateBlock.inter_arrival_time",
            levels=[4.0, 6.0]
        )
        
        factorial.add_factor(
            "service_capacity",
            "Resource.service.capacity",
            levels=[2, 3]
        )
        
        factorial.run_factorial_experiment(
            n_replications=2,
            simulation_time=50,
            warm_up_period=0,
            verbose=False
        )
        
        # 2 factors x 2 levels each x 2 replications = 8 runs
        assert len(factorial.results) == 8
        assert factorial.results_df is not None
    
    def test_run_factorial_3_factors(self):
        """Test running 2x2x2 factorial (3 factors)."""
        factorial = FactorialExperiment(
            simulation_function=configurable_simulation,
            base_seed=123
        )
        
        factorial.add_factor("arrival_rate", "path", [4.0, 6.0])
        factorial.add_factor("service_capacity", "path", [2, 3])
        
        factorial.run_factorial_experiment(
            n_replications=1,
            simulation_time=30,
            warm_up_period=0,
            verbose=False
        )
        
        # 2x2 = 4 combinations, 1 replication each = 4 runs
        assert len(factorial.results) == 4
    
    def test_get_aggregated_results(self):
        """Test aggregating results by factor combination."""
        factorial = FactorialExperiment(
            simulation_function=configurable_simulation,
            base_seed=123
        )
        
        factorial.add_factor("arrival_rate", "path", levels=[4.0, 6.0])
        factorial.add_factor("service_capacity", "path", levels=[2, 3])
        
        factorial.run_factorial_experiment(
            n_replications=3,
            simulation_time=50,
            warm_up_period=0,
            verbose=False
        )
        
        aggregated = factorial.get_aggregated_results()
        
        assert aggregated is not None
        # Should have 4 factor combinations (2x2)
        assert len(aggregated) == 4
    
    def test_extract_results(self):
        """Test extracting results from model."""
        model = configurable_simulation(
            arrival_rate=5.0,
            service_capacity=2,
            seed=123,
            until=50
        )
        
        factorial = FactorialExperiment(
            simulation_function=configurable_simulation
        )
        
        config = {"arrival_rate": 5.0, "service_capacity": 2}
        result = factorial._extract_results(model, config, combo_idx=0, rep=0)
        
        assert 'combination_id' in result
        assert 'replication' in result
        assert 'arrival_rate' in result
        assert 'service_capacity' in result
        assert 'entities_processed' in result
        assert result['arrival_rate'] == 5.0
        assert result['service_capacity'] == 2
        assert result['combination_id'] == 0
        assert result['replication'] == 0
    
    def test_factorial_with_single_factor(self):
        """Test factorial with only one factor."""
        factorial = FactorialExperiment(
            simulation_function=configurable_simulation,
            base_seed=123
        )
        
        factorial.add_factor(
            "arrival_rate",
            "path",
            levels=[3.0, 5.0, 7.0]
        )
        
        factorial.run_factorial_experiment(
            n_replications=2,
            simulation_time=30,
            warm_up_period=0,
            verbose=False
        )
        
        # 3 levels x 2 replications = 6 runs
        assert len(factorial.results) == 6
    
    def test_print_summary(self, capsys):
        """Test printing factorial summary."""
        factorial = FactorialExperiment(
            simulation_function=configurable_simulation,
            base_seed=123
        )
        
        factorial.add_factor("arrival_rate", "path", [4.0, 6.0])
        factorial.add_factor("service_capacity", "path", [2, 3])
        
        factorial.run_factorial_experiment(
            n_replications=2,
            simulation_time=30,
            warm_up_period=0,
            verbose=False
        )
        
        factorial.print_summary()
        
        captured = capsys.readouterr()
        assert "SUMMARY OF FACTORIAL ANALYSIS" in captured.out
        assert "TESTED FACTORS" in captured.out
    
    def test_export_results(self, tmp_path):
        """Test exporting factorial results."""
        factorial = FactorialExperiment(
            simulation_function=configurable_simulation,
            base_seed=123
        )
        
        factorial.add_factor("arrival_rate", "path", [4.0, 6.0])
        
        factorial.run_factorial_experiment(
            n_replications=2,
            simulation_time=30,
            warm_up_period=0,
            verbose=False
        )
        
        csv_file = tmp_path / "factorial_results.csv"
        factorial.export_results(str(csv_file))
        
        assert csv_file.exists()
        
        df = pd.read_csv(csv_file)
        assert len(df) == 4  # 2 levels x 2 replications
    
    def test_results_dataframe_structure(self):
        """Test structure of results DataFrame."""
        factorial = FactorialExperiment(
            simulation_function=configurable_simulation,
            base_seed=123
        )
        
        factorial.add_factor("arrival_rate", "path", [4.0, 6.0])
        
        factorial.run_factorial_experiment(
            n_replications=1,
            simulation_time=30,
            warm_up_period=0,
            verbose=False
        )
        
        df = factorial.results_df
        
        assert 'arrival_rate' in df.columns
        assert 'combination_id' in df.columns
        assert 'replication' in df.columns
        assert 'entities_processed' in df.columns
    
    def test_no_factors_defined(self):
        """Test running experiment without defining factors."""
        factorial = FactorialExperiment(
            simulation_function=configurable_simulation
        )
        
        # Should handle gracefully
        factorial.run_factorial_experiment(
            n_replications=1,
            simulation_time=30,
            verbose=False
        )
        
        # Should print warning or handle empty factors
        assert len(factorial.factors) == 0 
    
    def test_get_aggregated_results(self):
        """Test aggregating results by factor combination."""
        factorial = FactorialExperiment(
            simulation_function=configurable_simulation,
            base_seed=123
        )
        
        factorial.add_factor("arrival_rate", "path", levels=[4.0, 6.0])
        factorial.add_factor("service_capacity", "path", levels=[2, 3])
        
        factorial.run_factorial_experiment(
            n_replications=3,
            simulation_time=50,
            warm_up_period=0,
            verbose=False
        )
        
        aggregated = factorial.get_aggregated_results()
        
        assert aggregated is not None
        # Should have 4 factor combinations (2x2)
        assert len(aggregated) == 4
    
    def test_extract_results(self):
        """Test extracting results from model."""
        model = configurable_simulation(
            arrival_rate=5.0,
            service_capacity=2,
            seed=123,
            until=50
        )
        
        factorial = FactorialExperiment(
            simulation_function=configurable_simulation
        )
        
        config = {"arrival_rate": 5.0, "service_capacity": 2}
        result = factorial._extract_results(model, config, combo_idx=0, rep=0)
        
        assert 'combination_id' in result
        assert 'replication' in result
        assert 'arrival_rate' in result
        assert 'service_capacity' in result
        assert 'entities_processed' in result
        assert result['arrival_rate'] == 5.0
        assert result['service_capacity'] == 2
    
    def test_factorial_with_single_factor(self):
        """Test factorial with only one factor."""
        factorial = FactorialExperiment(
            simulation_function=configurable_simulation,
            base_seed=123
        )
        
        factorial.add_factor(
            "arrival_rate",
            "path",
            levels=[3.0, 5.0, 7.0]
        )
        
        factorial.run_factorial_experiment(
            n_replications=2,
            simulation_time=30,
            warm_up_period=0,
            verbose=False
        )
        
        # 3 levels x 2 replications = 6 runs
        assert len(factorial.results) == 6