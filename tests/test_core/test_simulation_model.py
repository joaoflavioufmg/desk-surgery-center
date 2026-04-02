# tests/test_core/test_simulation_model.py
import pytest
import simpy
from desk.core.simulation_model import SimulationModel
from desk.blocks.create_block import CreateBlock
from desk.blocks.dispose_block import DisposeBlock
from desk.blocks.process_block import ProcessBlock


class TestSimulationModel:
    """Test SimulationModel class functionality."""
    
    def test_model_creation(self):
        """Test creating a simulation model."""
        model = SimulationModel()
        
        assert isinstance(model.env, simpy.Environment)
        assert model.env.model == model
        assert model.blocks == {}
        assert model.resources == {}
        assert model.create_blocks == []
        assert model.dispose_blocks == []
        assert model.stability_result is None
        assert model.warm_up_period == 0.0
        assert model.is_warm_up_complete is False
    
    def test_add_resource_regular(self):
        """Test adding a regular resource."""
        model = SimulationModel()
        
        resource = model.add_resource("nurses", capacity=3, resource_type="regular")
        
        assert "nurses" in model.resources
        assert isinstance(resource, simpy.Resource)
        assert resource.capacity == 3
    
    def test_add_resource_priority(self):
        """Test adding a priority resource."""
        model = SimulationModel()
        
        resource = model.add_resource("doctors", capacity=2, resource_type="priority")
        
        assert "doctors" in model.resources
        assert isinstance(resource, simpy.PriorityResource)
        assert resource.capacity == 2
    
    def test_add_resource_preemptive(self):
        """Test adding a preemptive resource."""
        model = SimulationModel()
        
        resource = model.add_resource("equipment", capacity=1, resource_type="preemptive")
        
        assert "equipment" in model.resources
        assert isinstance(resource, simpy.PreemptiveResource)
        assert resource.capacity == 1
    
    def test_add_block(self):
        """Test adding blocks to model."""
        model = SimulationModel()
        
        create_block = CreateBlock(
            "Arrivals", model.env,
            inter_arrival_time=lambda: 1.0,
            max_arrivals=10
        )
        
        model.add_block(create_block)
        
        assert "Arrivals" in model.blocks
        assert len(model.create_blocks) == 1
    
    def test_add_dispose_block(self):
        """Test adding dispose block."""
        model = SimulationModel()
        
        dispose_block = DisposeBlock("Exit", model.env)
        model.add_block(dispose_block)
        
        assert "Exit" in model.blocks
        assert len(model.dispose_blocks) == 1
    
    def test_connect_blocks(self):
        """Test connecting two blocks."""
        model = SimulationModel()
        
        create_block = CreateBlock(
            "Arrivals", model.env,
            inter_arrival_time=lambda: 1.0,
            max_arrivals=5
        )
        dispose_block = DisposeBlock("Exit", model.env)
        
        model.add_block(create_block)
        model.add_block(dispose_block)
        model.connect_blocks("Arrivals", "Exit")
        
        assert create_block.next_block == dispose_block
    
    def test_connect_blocks_invalid(self):
        """Test connecting nonexistent blocks raises error."""
        model = SimulationModel()
        
        with pytest.raises(ValueError):
            model.connect_blocks("NonExistent1", "NonExistent2")
    
    def test_set_warm_up_period(self):
        """Test setting warm-up period."""
        model = SimulationModel()
        
        model.set_warm_up_period(100.0)
        
        assert model.warm_up_period == 100.0
        assert model.env.warm_up_period == 100.0
    
    def test_safe_delay_time_positive(self):
        """Test safe_delay_time with positive value."""
        model = SimulationModel()
        
        delay = model.safe_delay_time(lambda: 5.5)
        
        assert delay == 5.5
    
    def test_safe_delay_time_negative(self):
        """Test safe_delay_time replaces negative with zero."""
        model = SimulationModel()
        
        delay = model.safe_delay_time(lambda: -3.2)
        
        assert delay == 0.0
    
    def test_safe_delay_time_zero(self):
        """Test safe_delay_time with zero."""
        model = SimulationModel()
        
        delay = model.safe_delay_time(lambda: 0.0)
        
        assert delay == 0.0
    
    def test_entity_count_property(self):
        """Test entity_count property."""
        model = SimulationModel()
        
        dispose_block = DisposeBlock("Exit", model.env)
        model.add_block(dispose_block)
        
        # Simulate disposing some entities
        dispose_block.entities_disposed = 15
        
        assert model.entity_count == 15
    
    def test_overall_throughput(self):

        """Test overall_throughput calculation."""
        model = SimulationModel()
        model.env._now = 100.0  # Set current time
        model.warm_up_period = 20.0
        
        dispose_block = DisposeBlock("Exit", model.env)
        model.add_block(dispose_block)
        dispose_block.entities_disposed = 40
        
        # Throughput = entities / effective_time = 40 / (100 - 20) = 0.5
        assert model.overall_throughput == 0.5

    def test_get_results_structure(self):
        """Test get_results returns proper structure."""
        model = SimulationModel()
        model.env._now = 50.0
        
        create_block = CreateBlock(
            "Arrivals", model.env,
            inter_arrival_time=lambda: 1.0,
            max_arrivals=10
        )
        model.add_block(create_block)
        
        results = model.get_results()
        
        assert "simulation_time" in results
        assert "warm_up_period" in results
        assert "entity_count" in results
        assert "throughput" in results
        assert "blocks" in results
        assert "Arrivals" in results["blocks"]