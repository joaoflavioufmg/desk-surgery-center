# tests/test_analytics/test_plotting.py
import pytest
import simpy
from desk.analytics.plotting import SimulationPlotter
from desk.core.simulation_model import SimulationModel
from desk.blocks.process_block import ProcessBlock
from desk.blocks.dispose_block import DisposeBlock
from desk.core.entity import Entity


class TestSimulationPlotter:
    """Test SimulationPlotter functionality."""
    
    def test_plotter_initialization(self):
        """Test creating simulation plotter."""
        model = SimulationModel()
        plotter = SimulationPlotter(model)
        
        assert plotter.model == model
    
    def test_group_blocks_by_resource(self):
        """Test grouping blocks by resource."""
        model = SimulationModel()
        
        resource1 = model.add_resource("res1", capacity=2)
        resource2 = model.add_resource("res2", capacity=3)
        
        process1 = ProcessBlock("P1", model.env, resource=resource1, delay_time=lambda: 1.0)
        process2 = ProcessBlock("P2", model.env, resource=resource2, delay_time=lambda: 1.0)
        process3 = ProcessBlock("P3", model.env, resource=resource1, delay_time=lambda: 1.0)
        
        model.add_block(process1)
        model.add_block(process2)
        model.add_block(process3)
        
        plotter = SimulationPlotter(model)
        grouped = plotter._group_blocks_by_resource()
        
        assert "res1" in grouped
        assert "res2" in grouped
        assert len(grouped["res1"]) == 2
        assert len(grouped["res2"]) == 1
    
    def test_find_resource_name(self):
        """Test finding resource name from object."""
        model = SimulationModel()
        
        resource = model.add_resource("test_resource", capacity=2)
        
        plotter = SimulationPlotter(model)
        name = plotter._find_resource_name(resource)
        
        assert name == "test_resource"
    
    def test_find_resource_name_not_found(self):
        """Test finding resource name that doesn't exist."""
        model = SimulationModel()
        
        # Create resource not registered in model
        unregistered = simpy.Resource(model.env, capacity=1)
        
        plotter = SimulationPlotter(model)
        name = plotter._find_resource_name(unregistered)
        
        assert name is None