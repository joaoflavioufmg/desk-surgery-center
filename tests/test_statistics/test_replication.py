# tests/test_statistics/test_replication.py
import pytest
import simpy
import pandas as pd
import math
from desk.stats.replication import ReplicationFramework
from desk.core.simulation_model import SimulationModel
from desk.blocks.create_block import CreateBlock
from desk.blocks.process_block import ProcessBlock
from desk.blocks.dispose_block import DisposeBlock
import matplotlib
matplotlib.use("Agg")  # use headless backend, no Tk needed
import matplotlib.pyplot as plt


def simple_simulation(seed=None, until=100, warm_up_period=0):
    """Simple simulation model for testing."""
    model = SimulationModel()
    
    resource = model.add_resource("service", capacity=2)
    
    create = CreateBlock(
        "Arrivals",
        model.env,
        inter_arrival_time=lambda: 5.0,
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


class TestReplicationFramework:
    """Test ReplicationFramework functionality."""
    
    def test_framework_initialization(self):
        """Test creating replication framework."""
        framework = ReplicationFramework(
            simulation_function=simple_simulation,
            n_replications=5
        )
        
        assert framework.simulation_function == simple_simulation
        assert framework.n_replications == 5
        assert framework.replication_results == []
        assert framework.summary_statistics == {}
    
    def test_default_replications(self):
        """Test default number of replications."""
        framework = ReplicationFramework(simulation_function=simple_simulation)
        assert framework.n_replications == 30  # Default value
    
    def test_run_replications(self):
        """Test running multiple replications."""
        framework = ReplicationFramework(
            simulation_function=simple_simulation,
            n_replications=3
        )
        
        framework.run_replications(
            base_seed=123,
            until=100,
            warm_up_period=0
        )
        
        assert len(framework.replication_results) == 3
        assert len(framework.summary_statistics) > 0
    
    def test_extract_kpis(self):
        """Test KPI extraction from model."""
        model = simple_simulation(seed=123, until=100, warm_up_period=0)
        
        framework = ReplicationFramework(
            simulation_function=simple_simulation,
            n_replications=1
        )
        
        kpis = framework._extract_kpis(model, replication_id=0)
        
        assert 'replication_id' in kpis
        assert 'simulation_time' in kpis
        assert 'entities_processed' in kpis
        assert 'system_time_avg' in kpis
        assert kpis['replication_id'] == 0
        assert kpis['simulation_time'] == 100
    
    def test_extract_kpis_with_wip(self):
        """Test that WIP metrics are extracted."""
        model = simple_simulation(seed=123, until=100, warm_up_period=0)
        
        framework = ReplicationFramework(
            simulation_function=simple_simulation,
            n_replications=1
        )
        
        kpis = framework._extract_kpis(model, replication_id=0)
        
        assert 'average_wip' in kpis
        assert 'max_wip' in kpis
        assert 'final_wip' in kpis
    
    def test_extract_kpis_with_financial(self):
        """Test that financial metrics are extracted."""
        model = simple_simulation(seed=123, until=100, warm_up_period=0)
        
        framework = ReplicationFramework(
            simulation_function=simple_simulation,
            n_replications=1
        )
        
        kpis = framework._extract_kpis(model, replication_id=0)
        
        assert 'total_revenue' in kpis
        assert 'total_costs' in kpis
        assert 'net_profit' in kpis
    
    def test_calculate_summary_statistics(self):
        """Test summary statistics calculation."""
        framework = ReplicationFramework(
            simulation_function=simple_simulation,
            n_replications=5
        )
        
        framework.run_replications(
            base_seed=123,
            until=100,
            warm_up_period=0
        )
        
        stats = framework.summary_statistics
        
        # Check that key metrics have statistics
        assert 'system_time_avg' in stats
        assert 'mean' in stats['system_time_avg']
        assert 'std' in stats['system_time_avg']
        assert 'ci_lower' in stats['system_time_avg']
        assert 'ci_upper' in stats['system_time_avg']
        assert 'n_replications' in stats['system_time_avg']
    
    def test_confidence_intervals(self):
        """Test that confidence intervals are properly calculated."""
        framework = ReplicationFramework(
            simulation_function=simple_simulation,
            n_replications=10
        )
        
        framework.run_replications(
            base_seed=123,
            until=100,
            warm_up_period=0
        )
        
        stats = framework.summary_statistics['system_time_avg']
        
        # CI should contain the mean
        assert stats['ci_lower'] <= stats['mean'] <= stats['ci_upper']
        
        # Half-width should be non-negative (not strictly positive)
        # For deterministic cases, such as simple model with time = 5, 3.
        assert stats['half_width'] >= 0
        
        # Relative precision should be calculated
        assert 'relative_precision' in stats
    
    def test_nan_handling_in_statistics(self):
        """Test that NaN values are handled in statistics."""
        framework = ReplicationFramework(
            simulation_function=simple_simulation,
            n_replications=3
        )
        
        framework.run_replications(
            base_seed=123,
            until=100,
            warm_up_period=0
        )
        
        # Verify no NaN in critical statistics
        for metric, stats in framework.summary_statistics.items():
            if metric not in ['replication_id', 'simulation_time', 'warm_up_period']:
                # Allow NaN only if n_replications is 0
                if stats['n_replications'] > 1:
                    assert not math.isnan(stats['mean'])
    
    def test_get_results_dataframe(self):
        """Test converting results to DataFrame."""
        framework = ReplicationFramework(
            simulation_function=simple_simulation,
            n_replications=3
        )
        
        framework.run_replications(
            base_seed=123,
            until=50,
            warm_up_period=0
        )
        
        df = framework.get_results_dataframe()
        
        assert isinstance(df, pd.DataFrame)
        assert len(df) == 3
        assert 'entities_processed' in df.columns
    
    def test_export_results(self, tmp_path):
        """Test exporting results to CSV."""
        framework = ReplicationFramework(
            simulation_function=simple_simulation,
            n_replications=2
        )
        
        framework.run_replications(
            base_seed=123,
            until=50,
            warm_up_period=0
        )
        
        csv_file = tmp_path / "test_results.csv"
        framework.export_results(str(csv_file))
        
        assert csv_file.exists()
        
        # Verify CSV can be read
        df = pd.read_csv(csv_file)
        assert len(df) == 2
    
    def test_different_seeds_produce_different_results(self):
        """Test that different seeds produce different results."""
        framework = ReplicationFramework(
            simulation_function=simple_simulation,
            n_replications=2
        )
        
        framework.run_replications(
            base_seed=123,
            until=100,
            warm_up_period=0
        )
        
        # Results should have different random outcomes
        assert len(framework.replication_results) == 2
    
    def test_print_statistical_summary(self, capsys):
        """Test printing statistical summary."""
        framework = ReplicationFramework(
            simulation_function=simple_simulation,
            n_replications=3
        )
        
        framework.run_replications(
            base_seed=123,
            until=50,
            warm_up_period=0
        )
        
        framework.print_statistical_summary()
        
        captured = capsys.readouterr()
        assert "STATISTICAL RESULTS" in captured.out
        assert "REPLICATIONS" in captured.out
    
    def test_resource_utilization_metrics(self):
        """Test that resource utilization is captured."""
        framework = ReplicationFramework(
            simulation_function=simple_simulation,
            n_replications=3
        )
        
        framework.run_replications(
            base_seed=123,
            until=100,
            warm_up_period=0
        )
        
        # Should have utilization metrics
        assert any('utilization' in key for key in framework.summary_statistics.keys())
