# tests/test_integration/test_validation_integration.py
import pytest
from desk.core.simulation_model import SimulationModel
from desk.blocks.create_block import CreateBlock
from desk.blocks.process_block import ProcessBlock
from desk.blocks.dispose_block import DisposeBlock
from desk.validation.resource_validator import ResourceValidationError


class TestValidationIntegration:
    """Integration tests for resource validation."""
    
    def test_validation_catches_overallocation(self):
        """Test that validation catches resource overallocation before simulation."""
        model = SimulationModel()
        
        # Create resource with capacity 2
        resource = model.add_resource("server", capacity=2)
        
        # Create process block requesting 3 units (MORE than capacity!)
        arrivals = CreateBlock(
            "Arrivals",
            model.env,
            inter_arrival_time=lambda: 5.0,
            max_arrivals=10
        )
        
        service = ProcessBlock(
            "Service",
            model.env,
            resource=resource,
            delay_time=lambda: 3.0,
            resource_units=3  # ERROR: Exceeds capacity!
        )
        
        exit_block = DisposeBlock("Exit", model.env)
        
        model.add_block(arrivals)
        model.add_block(service)
        model.add_block(exit_block)
        
        model.connect_blocks("Arrivals", "Service")
        model.connect_blocks("Service", "Exit")
        
        # Validation should raise error
        with pytest.raises(ResourceValidationError):
            model.run_simulation(
                validate_resources=True,  # Enable validation
                until=100,
                seed=123
            )
    
    def test_validation_passes_correct_config(self):
        """Test that validation passes for correct configuration."""
        model = SimulationModel()
        
        resource = model.add_resource("server", capacity=3)
        
        arrivals = CreateBlock(
            "Arrivals",
            model.env,
            inter_arrival_time=lambda: 5.0,
            max_arrivals=10
        )
        
        service = ProcessBlock(
            "Service",
            model.env,
            resource=resource,
            delay_time=lambda: 3.0,
            resource_units=2  # OK: Less than capacity
        )
        
        exit_block = DisposeBlock("Exit", model.env)
        
        model.add_block(arrivals)
        model.add_block(service)
        model.add_block(exit_block)
        
        model.connect_blocks("Arrivals", "Service")
        model.connect_blocks("Service", "Exit")
        
        # Should run without error
        model.run_simulation(
            validate_resources=True,
            until=100,
            seed=123
        )
        
        assert service.entities_processed > 0
    
    def test_model_with_warm_up(self):
        """Test that the warm-up period correctly resets statistics."""
        model = SimulationModel()
        
        # Setup resources and blocks
        resource = model.add_resource("server", capacity=1)
        
        arrivals = CreateBlock(
            "Arrivals",
            model.env,
            inter_arrival_time=lambda: 5.0, # An entity arrives every 5 time units
            max_arrivals=10
        )
        
        service = ProcessBlock(
            "Service",
            model.env,
            resource=resource,
            delay_time=lambda: 3.0 # Service takes 3 time units
        )
        
        exit_block = DisposeBlock("Exit", model.env)
        
        # Add and connect blocks
        model.add_block(arrivals)
        model.add_block(service)
        model.add_block(exit_block)
        model.connect_blocks("Arrivals", "Service")
        model.connect_blocks("Service", "Exit")
        
        # Run simulation with a warm-up period
        # Arrivals at: 0, 5, 10, 15, 20
        # Service finishes at: 3, 8, 13, 18, 23
        # With a warm-up of 9.0, entities finishing at 3 and 8 are 'warm-up'.
        # Entities finishing at 13, 18, 23 are post-warm-up.
        # Therefore, we expect 3 entities to be counted in the final stats.
        model.run_simulation(
            until=25.0,
            warm_up_period=9.0,
            seed=123
        )
        
        # Verify that only post-warm-up entities are counted in final statistics
        assert exit_block.entities_disposed == 3
        assert service.entities_processed == 3
        
        # Total entities that passed through the block (including warm-up) should be higher
        assert len(exit_block.disposed_entities) == 5