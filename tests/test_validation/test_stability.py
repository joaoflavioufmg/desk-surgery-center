# tests/test_validation/test_stability.py
import pytest
import simpy
from desk.validation.stability import StabilityAnalyzer
from desk.core.simulation_model import SimulationModel
from desk.blocks.create_block import CreateBlock
from desk.blocks.process_block import ProcessBlock, MultiProcessBlock
from desk.blocks.dispose_block import DisposeBlock


class TestStabilityAnalyzer:
    """Test StabilityAnalyzer functionality."""
    
    def test_analyzer_initialization(self):
        """Test creating stability analyzer."""
        model = SimulationModel()
        analyzer = StabilityAnalyzer(model)
        
        assert analyzer.model == model
    
    def test_stable_system(self):
        """Test detection of stable system (capacity > demand)."""
        model = SimulationModel()
        
        # Low arrival rate, high capacity
        create = CreateBlock(
            "Arrivals",
            model.env,
            inter_arrival_time=lambda: 10.0,  # 1 every 10 min
            max_arrivals=10
        )
        
        resource = model.add_resource("service", capacity=5)
        process = ProcessBlock(
            "Service",
            model.env,
            resource=resource,
            delay_time=lambda: 5.0  # 5 min service
        )
        
        dispose = DisposeBlock("Exit", model.env)
        
        model.add_block(create)
        model.add_block(process)
        model.add_block(dispose)
        
        model.connect_blocks("Arrivals", "Service")
        model.connect_blocks("Service", "Exit")
        
        analyzer = StabilityAnalyzer(model)
        stability = analyzer.check_system_stability(sample_size=100)
        
        # System should be stable (capacity exceeds demand)
        assert stability > 1.0
    
    def test_unstable_system(self):
        """Test detection of unstable system (demand > capacity)."""
        model = SimulationModel()
        
        # High arrival rate, low capacity
        create = CreateBlock(
            "Arrivals",
            model.env,
            inter_arrival_time=lambda: 1.0,  # 1 per minute
            max_arrivals=10
        )
        
        resource = model.add_resource("service", capacity=1)
        process = ProcessBlock(
            "Service",
            model.env,
            resource=resource,
            delay_time=lambda: 10.0  # 10 min service
        )
        
        dispose = DisposeBlock("Exit", model.env)
        
        model.add_block(create)
        model.add_block(process)
        model.add_block(dispose)
        
        model.connect_blocks("Arrivals", "Service")
        model.connect_blocks("Service", "Exit")
        
        analyzer = StabilityAnalyzer(model)
        stability = analyzer.check_system_stability(sample_size=100)
        
        # System should be unstable (demand exceeds capacity)
        assert stability < 1.0
    
    def test_calculate_arrival_rate(self):
        """Test arrival rate calculation."""
        model = SimulationModel()
        
        create = CreateBlock(
            "Arrivals",
            model.env,
            inter_arrival_time=lambda: 5.0,  # Fixed 5 min
            max_arrivals=10
        )
        
        model.add_block(create)
        
        analyzer = StabilityAnalyzer(model)
        arrival_rate = analyzer._calculate_arrival_rate(sample_size=100)
        
        # Arrival rate should be approximately 1/5 = 0.2 per minute
        assert 0.15 < arrival_rate < 0.25
    
    def test_multiple_create_blocks(self):
        """Test with multiple arrival streams."""
        model = SimulationModel()
        
        create1 = CreateBlock(
            "Arrivals1",
            model.env,
            inter_arrival_time=lambda: 10.0,
            max_arrivals=10
        )
        
        create2 = CreateBlock(
            "Arrivals2",
            model.env,
            inter_arrival_time=lambda: 10.0,
            max_arrivals=10
        )
        
        resource = model.add_resource("service", capacity=2)
        process = ProcessBlock(
            "Service",
            model.env,
            resource=resource,
            delay_time=lambda: 5.0
        )
        
        model.add_block(create1)
        model.add_block(create2)
        model.add_block(process)
        
        analyzer = StabilityAnalyzer(model)
        total_rate = analyzer._calculate_arrival_rate(sample_size=100)
        
        # Should sum arrival rates from both streams
        assert total_rate > 0.15  # Combined rate should be ~0.2
    
    def test_find_bottleneck(self):
        """Test finding bottleneck resource."""
        model = SimulationModel()
        
        create = CreateBlock(
            "Arrivals",
            model.env,
            inter_arrival_time=lambda: 5.0,
            max_arrivals=10
        )
        
        # Two resources with different capacities
        resource1 = model.add_resource("fast_service", capacity=5)
        resource2 = model.add_resource("slow_service", capacity=1)  # Bottleneck
        
        process1 = ProcessBlock(
            "Service1",
            model.env,
            resource=resource1,
            delay_time=lambda: 2.0
        )
        
        process2 = ProcessBlock(
            "Service2",
            model.env,
            resource=resource2,
            delay_time=lambda: 3.0
        )
        
        model.add_block(create)
        model.add_block(process1)
        model.add_block(process2)
        
        analyzer = StabilityAnalyzer(model)
        bottleneck_rate, bottleneck_name = analyzer._find_bottleneck(sample_size=100)
        
        # Bottleneck should be the slower resource
        assert bottleneck_name == "slow_service"
    
    def test_print_stability_assessment(self, capsys):
        """Test stability assessment printing."""
        model = SimulationModel()
        analyzer = StabilityAnalyzer(model)
        
        # Test different stability levels
        analyzer._print_stability_assessment(1.3)  # Super dimensioned
        captured = capsys.readouterr()
        assert "Oversized" in captured.out
        
        analyzer._print_stability_assessment(1.1)  # Stable
        captured = capsys.readouterr()
        assert "Stable" in captured.out
        
        analyzer._print_stability_assessment(0.5)  # Unstable
        captured = capsys.readouterr()
        assert "COLLAPSE" in captured.out or "UNSTABLE" in captured.out
    
    def test_group_process_blocks_by_resource(self):
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
        
        analyzer = StabilityAnalyzer(model)
        grouped = analyzer._group_process_blocks_by_resource()
        
        assert "res1" in grouped
        assert "res2" in grouped
        assert len(grouped["res1"]) == 2  # P1 and P3
        assert len(grouped["res2"]) == 1  # P2
    
    def test_calculate_resource_rate(self):
        """Test resource service rate calculation."""
        model = SimulationModel()
        
        resource = model.add_resource("service", capacity=2)
        
        process1 = ProcessBlock(
            "Service1",
            model.env,
            resource=resource,
            delay_time=lambda: 5.0  # 5 min service time
        )
        
        model.add_block(process1)
        
        analyzer = StabilityAnalyzer(model)
        rate = analyzer._calculate_resource_rate([process1], sample_size=100)
        
        # Service rate should be approximately 1/5 = 0.2 per minute
        assert 0.15 < rate < 0.25