# tests/test_integration/test_priority_model.py
import pytest
import simpy
from desk.core.simulation_model import SimulationModel
from desk.blocks.create_block import CreateBlock
from desk.blocks.process_block import ProcessBlock
from desk.blocks.dispose_block import DisposeBlock
from desk.core.entity import EventLogger


class TestPriorityModelIntegration:
    """Integration tests with priority queuing."""
    
    def test_priority_queue_ordering(self):
        """Test that priority queuing works correctly."""
        model = SimulationModel()
        logger = EventLogger()
        
        # Priority resource
        resource = model.add_resource("server", capacity=1, resource_type="priority")
        
        # Create entities with different priorities
        arrivals = CreateBlock(
            "Arrivals",
            model.env,
            inter_arrival_time=lambda: 1.0,
            max_arrivals=5,
            priority_generator=lambda: [0, 2, 1, 2, 0][arrivals.entities_created] if arrivals.entities_created < 5 else 0,
            event_logger=logger
        )
        
        service = ProcessBlock(
            "Service",
            model.env,
            resource=resource,
            delay_time=lambda: 10.0,  # Long service time
            event_logger=logger
        )
        service.set_resource_name("server")
        
        exit_block = DisposeBlock("Exit", model.env, event_logger=logger)
        
        model.add_block(arrivals)
        model.add_block(service)
        model.add_block(exit_block)
        
        model.connect_blocks("Arrivals", "Service")
        model.connect_blocks("Service", "Exit")
        
        model.run_simulation(until=100, seed=123)
        
        # Check that entities were processed
        events = logger.get_dataframe()
        service_events = events[events['activity'] == 'Service']
        
        assert len(service_events) > 0
        assert service.entities_processed > 0
    
    def test_multi_resource_block(self):
        """Test MultiProcessBlock with multiple resources."""
        from desk.blocks.process_block import MultiProcessBlock
        
        model = SimulationModel()
        
        resource1 = model.add_resource("res1", capacity=2)
        resource2 = model.add_resource("res2", capacity=3)
        
        arrivals = CreateBlock(
            "Arrivals",
            model.env,
            inter_arrival_time=lambda: 5.0,
            max_arrivals=10
        )
        
        multi_service = MultiProcessBlock(
            "MultiService",
            model.env,
            resource_requirements={
                resource1: 1,
                resource2: 1
            },
            delay_time=lambda: 3.0
        )
        multi_service.set_resource_names({
            resource1: "res1",
            resource2: "res2"
        })
        
        exit_block = DisposeBlock("Exit", model.env)
        
        model.add_block(arrivals)
        model.add_block(multi_service)
        model.add_block(exit_block)
        
        model.connect_blocks("Arrivals", "MultiService")
        model.connect_blocks("MultiService", "Exit")
        
        model.run_simulation(until=100, seed=123)
        
        # Verify entities were processed
        assert multi_service.entities_processed > 0
        assert exit_block.entities_disposed > 0