# tests/test_validation/test_resource_validator.py
import pytest
import simpy
from desk.validation.resource_validator import ResourceValidator, ResourceValidationError
from desk.core.simulation_model import SimulationModel
from desk.blocks.process_block import ProcessBlock, MultiProcessBlock
from desk.blocks.dispose_block import DisposeBlock


class TestResourceValidator:
    """Test ResourceValidator functionality."""
    
    def test_validator_initialization(self):
        """Test creating resource validator."""
        model = SimulationModel()
        validator = ResourceValidator(model)
        
        assert validator.model == model
        assert validator.errors == []
        assert validator.warnings == []
    
    def test_valid_configuration(self):
        """Test validation of correct configuration."""
        model = SimulationModel()
        
        resource = model.add_resource("service", capacity=3)
        process = ProcessBlock(
            "Service",
            model.env,
            resource=resource,
            delay_time=lambda: 1.0,
            resource_units=2  # Less than capacity
        )
        
        model.add_block(process)
        
        validator = ResourceValidator(model)
        is_valid = validator.validate_all(raise_on_error=False)
        
        assert is_valid
        assert len(validator.errors) == 0
    
    def test_overallocation_error(self):
        """Test detection of resource overallocation."""
        model = SimulationModel()
        
        resource = model.add_resource("service", capacity=2)
        process = ProcessBlock(
            "Service",
            model.env,
            resource=resource,
            delay_time=lambda: 1.0,
            resource_units=3  # EXCEEDS capacity!
        )
        
        model.add_block(process)
        
        validator = ResourceValidator(model)
        is_valid = validator.validate_all(raise_on_error=False)
        
        assert not is_valid
        assert len(validator.errors) > 0
        assert "OVER ALLOCATION" in validator.errors[0]
    
    def test_overallocation_raises_exception(self):
        """Test that overallocation raises exception when requested."""
        model = SimulationModel()
        
        resource = model.add_resource("service", capacity=2)
        process = ProcessBlock(
            "Service",
            model.env,
            resource=resource,
            delay_time=lambda: 1.0,
            resource_units=5
        )
        
        model.add_block(process)
        
        validator = ResourceValidator(model)
        
        with pytest.raises(ResourceValidationError):
            validator.validate_all(raise_on_error=True)
    
    def test_high_capacity_warning(self):
        """Test warning for unusually high capacity."""
        model = SimulationModel()
        
        # Very high capacity
        resource = model.add_resource("service", capacity=2000)
        
        validator = ResourceValidator(model)
        validator.validate_all(raise_on_error=False)
        
        assert len(validator.warnings) > 0
        assert any("HIGH CAPACITY" in w for w in validator.warnings)
    
    def test_invalid_capacity_error(self):
        """Test error for invalid capacity."""
        model = SimulationModel()
        
        # Manually create resource with zero capacity for testing
        resource = simpy.Resource(model.env, capacity=1)
        # Force invalid capacity for testing
        # Directly modify private attribute (OK in test context)
        resource._capacity = 0  # ⚠️ underscore attribute
        
        model.resources["invalid"] = resource
        
        
        validator = ResourceValidator(model)
        is_valid = validator.validate_all(raise_on_error=False)
        
        assert not is_valid
        # assert len(validator.errors) > 0
        assert any("capacity" in err.lower() for err in validator.errors)
    
    def test_multi_process_block_validation(self):
        """Test validation of MultiProcessBlock."""
        model = SimulationModel()
        
        res1 = model.add_resource("res1", capacity=2)
        res2 = model.add_resource("res2", capacity=3)
        
        multi_process = MultiProcessBlock(
            "MultiService",
            model.env,
            resource_requirements={
                res1: 1,  # OK
                res2: 4   # EXCEEDS capacity!
            },
            delay_time=lambda: 1.0
        )
        
        model.add_block(multi_process)
        
        validator = ResourceValidator(model)
        is_valid = validator.validate_all(raise_on_error=False)
        
        assert not is_valid
        assert len(validator.errors) > 0
    
    def test_unregistered_resource_error(self):
        """Test error for unregistered resource."""
        model = SimulationModel()
        
        # Create resource but don't register it
        unregistered_resource = simpy.Resource(model.env, capacity=2)
        
        process = ProcessBlock(
            "Service",
            model.env,
            resource=unregistered_resource,
            delay_time=lambda: 1.0
        )
        
        model.add_block(process)
        
        validator = ResourceValidator(model)
        is_valid = validator.validate_all(raise_on_error=False)
        
        assert not is_valid
        assert any("UNREGISTERED" in e for e in validator.errors)
    
    def test_full_resource_use_warning(self):
        """Test warning when using full resource capacity."""
        model = SimulationModel()
        
        resource = model.add_resource("service", capacity=3)
        process = ProcessBlock(
            "Service",
            model.env,
            resource=resource,
            delay_time=lambda: 1.0,
            resource_units=3  # Uses ALL capacity
        )
        
        model.add_block(process)
        
        validator = ResourceValidator(model)
        validator.validate_all(raise_on_error=False)
        
        assert len(validator.warnings) > 0
        assert any("FULL RESOURCE" in w for w in validator.warnings)
    
    def test_high_resource_use_warning(self):
        """Test warning for high resource use (>50%)."""
        model = SimulationModel()
        
        resource = model.add_resource("service", capacity=10)
        process = ProcessBlock(
            "Service",
            model.env,
            resource=resource,
            delay_time=lambda: 1.0,
            resource_units=6  # 60% of capacity
        )
        
        model.add_block(process)
        
        validator = ResourceValidator(model)
        validator.validate_all(raise_on_error=False)
        
        assert len(validator.warnings) > 0
        assert any("HIGH RESOURCE USE" in w for w in validator.warnings)
    
    def test_print_resource_summary(self, capsys):
        """Test printing resource summary."""
        model = SimulationModel()
        
        resource = model.add_resource("nurses", capacity=5)
        process = ProcessBlock(
            "Service",
            model.env,
            resource=resource,
            delay_time=lambda: 1.0,
            resource_units=2
        )
        
        model.add_block(process)
        
        validator = ResourceValidator(model)
        validator.print_resource_summary()
        
        captured = capsys.readouterr()
        assert "RESOURCE CONFIGURATION SUMMARY" in captured.out
        assert "nurses" in captured.out
        assert "Capacity: 5" in captured.out
    
    def test_validate_resource_types(self):
        """Test validation of different resource types."""
        model = SimulationModel()
        
        # Priority resource
        priority_res = model.add_resource("priority", capacity=2, resource_type="priority")
        
        # Regular resource
        regular_res = model.add_resource("regular", capacity=2, resource_type="regular")
        
        validator = ResourceValidator(model)
        is_valid = validator.validate_all(raise_on_error=False)
        
        assert is_valid
    
    def test_get_resource_type_name(self):
        """Test getting resource type name."""
        model = SimulationModel()
        validator = ResourceValidator(model)
        
        regular = simpy.Resource(model.env, capacity=1)
        priority = simpy.PriorityResource(model.env, capacity=1)
        preemptive = simpy.PreemptiveResource(model.env, capacity=1)
        
        assert validator._get_resource_type_name(regular) == "Resource"
        assert validator._get_resource_type_name(priority) == "PriorityResource"
        assert validator._get_resource_type_name(preemptive) == "PreemptiveResource"
    
    def test_format_error_message(self):
        """Test error message formatting."""
        model = SimulationModel()
        
        resource = model.add_resource("service", capacity=1)
        process = ProcessBlock(
            "Service",
            model.env,
            resource=resource,
            delay_time=lambda: 1.0,
            resource_units=3
        )
        
        model.add_block(process)
        
        validator = ResourceValidator(model)
        validator.validate_all(raise_on_error=False)
        
        error_msg = validator._format_error_message()
        
        assert "CRITICAL RESOURCE CONFIGURATION ERROR" in error_msg
        assert "FIX THESE ERRORS" in error_msg