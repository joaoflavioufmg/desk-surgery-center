# tests/test_analytics/test_reporting.py
import pytest
import simpy
from desk.analytics.reporting import SimulationReporter
from desk.core.simulation_model import SimulationModel
from desk.blocks.create_block import CreateBlock
from desk.blocks.dispose_block import DisposeBlock


class TestSimulationReporter:
    """Test SimulationReporter functionality."""
    
    def test_reporter_initialization(self):
        """Test creating simulation reporter."""
        model = SimulationModel()
        reporter = SimulationReporter(model)
        
        assert reporter.model == model
        assert reporter.HOURS == 60
        assert reporter.DAYS == 1440
    
    def test_print_results(self, capsys):
        """Test printing results."""
        model = SimulationModel()
        model.env._now = 120.0  # 2 hours
        
        create = CreateBlock(
            "Arrivals",
            model.env,
            inter_arrival_time=lambda: 1.0,
            max_arrivals=10
        )
        dispose = DisposeBlock("Exit", model.env)
        
        model.add_block(create)
        model.add_block(dispose)
        
        reporter = SimulationReporter(model)
        reporter.print_results()
        
        captured = capsys.readouterr()
        assert "SIMULATION RESULTS" in captured.out
        assert "Duration:" in captured.out
    
    def test_wip_metrics_printed(self, capsys):
        """Test that WIP metrics are included in results."""
        model = SimulationModel()
        model.env._now = 100.0
        
        dispose = DisposeBlock("Exit", model.env)
        model.add_block(dispose)
        
        reporter = SimulationReporter(model)
        reporter._print_wip_metrics()
        
        captured = capsys.readouterr()
        assert "WORK IN PROCESS" in captured.out or "WIP" in captured.out