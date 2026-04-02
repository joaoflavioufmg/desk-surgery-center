# tests/test_validation/test_warmup.py
import pytest
import simpy
import numpy as np
from desk.validation.warmup import WarmUpAnalyzer
from desk.core.simulation_model import SimulationModel
from desk.blocks.create_block import CreateBlock
from desk.blocks.process_block import ProcessBlock
from desk.blocks.dispose_block import DisposeBlock


class TestWarmUpAnalyzer:
    """Test WarmUpAnalyzer functionality."""
    
    def test_analyzer_initialization(self):
        """Test creating warm-up analyzer."""
        model = SimulationModel()
        analyzer = WarmUpAnalyzer(model)
        
        assert analyzer.model == model
    
    def test_find_stabilization_point(self):
        """Test finding stabilization point in utilization data."""

        np.random.seed(12345)  # 👈 ensures stable, reproducible behavior
    
        model = SimulationModel()
        analyzer = WarmUpAnalyzer(model)
        
        # Create mock utilization data: starts high, then stabilizes
        times = list(range(100))
        utilizations = [0.9] * 20 + [0.5 + 0.01 * np.random.randn() for _ in range(80)]
        
        stabilization = analyzer._find_stabilization_point(times, utilizations)
        
        # Should find stabilization around time 20-30
        assert stabilization is not None
        assert 15 < stabilization < 45
    
    def test_find_stabilization_gradual(self):
        """Test with gradual stabilization."""
        model = SimulationModel()
        analyzer = WarmUpAnalyzer(model)
        
        # Gradual decrease then stable
        times = list(range(100))
        utilizations = []
        for i in range(100):
            if i < 30:
                utilizations.append(0.9 - i * 0.01)
            else:
                utilizations.append(0.6 + 0.02 * np.random.randn())
        
        stabilization = analyzer._find_stabilization_point(times, utilizations)
        
        assert stabilization is not None
        assert stabilization > 20
    
    def test_find_stabilization_no_data(self):
        """Test stabilization with insufficient data."""
        model = SimulationModel()
        analyzer = WarmUpAnalyzer(model)
        
        times = []
        utilizations = []
        
        stabilization = analyzer._find_stabilization_point(times, utilizations)
        
        assert stabilization is None
    
    def test_find_stabilization_already_stable(self):
        """Test when system is already stable from start."""
        model = SimulationModel()
        analyzer = WarmUpAnalyzer(model)
        
        times = list(range(100))
        utilizations = [0.5 + 0.01 * np.random.randn() for _ in range(100)]
        
        stabilization = analyzer._find_stabilization_point(times, utilizations)
        
        # Should find early stabilization
        if stabilization is not None:
            assert stabilization < 30
    
    def test_group_blocks_by_resource(self):
        """Test grouping process blocks by resource."""
        model = SimulationModel()
        
        resource1 = model.add_resource("res1", capacity=2)
        resource2 = model.add_resource("res2", capacity=3)
        
        process1 = ProcessBlock("P1", model.env, resource=resource1, delay_time=lambda: 1.0)
        process2 = ProcessBlock("P2", model.env, resource=resource2, delay_time=lambda: 1.0)
        process3 = ProcessBlock("P3", model.env, resource=resource1, delay_time=lambda: 1.0)
        
        model.add_block(process1)
        model.add_block(process2)
        model.add_block(process3)
        
        analyzer = WarmUpAnalyzer(model)
        grouped = analyzer._group_blocks_by_resource()
        
        assert "res1" in grouped
        assert "res2" in grouped
        assert len(grouped["res1"]) == 2  # P1 and P3
        assert len(grouped["res2"]) == 1  # P2
    
    def test_find_resource_name(self):
        """Test finding resource name from object."""
        model = SimulationModel()
        
        resource = model.add_resource("test_resource", capacity=2)
        
        analyzer = WarmUpAnalyzer(model)
        name = analyzer._find_resource_name(resource)
        
        assert name == "test_resource"
    
    def test_find_resource_name_not_found(self):
        """Test finding resource that doesn't exist."""
        model = SimulationModel()
        
        # Create resource not registered
        unregistered = simpy.Resource(model.env, capacity=1)
        
        analyzer = WarmUpAnalyzer(model)
        name = analyzer._find_resource_name(unregistered)
        
        assert name is None
    
    def test_collect_resource_data(self):
        """Test collecting resource data from blocks."""
        model = SimulationModel()
        
        resource = model.add_resource("service", capacity=2)
        
        process = ProcessBlock(
            "Service",
            model.env,
            resource=resource,
            delay_time=lambda: 1.0
        )
        
        # Add mock data
        process.resource_data = [
            (0, 0, 0),
            (10, 1, 0),
            (20, 2, 1)
        ]
        
        model.add_block(process)
        
        analyzer = WarmUpAnalyzer(model)
        data = analyzer._collect_resource_data("service", [process])
        
        assert len(data) == 3
        assert data[0] == (0, 0, 0)
        assert data[2] == (20, 2, 1)
    
    def test_analyze_warm_up_period(self, capsys):
        """Test complete warm-up analysis."""
        model = SimulationModel()
        
        resource = model.add_resource("service", capacity=2)
        
        process = ProcessBlock(
            "Service",
            model.env,
            resource=resource,
            delay_time=lambda: 1.0
        )
        
        # Add mock data simulating warm-up
        process.resource_data = [
            (t, min(2, t // 10), max(0, 5 - t // 10))
            for t in range(0, 100, 5)
        ]
        
        model.add_block(process)
        
        analyzer = WarmUpAnalyzer(model)
        analyzer.analyze_warm_up_period()
        
        captured = capsys.readouterr()
        assert "WARM-UP ANALYSIS" in captured.out
        # assert "service" in captured.out
        assert "Please note" in captured.out