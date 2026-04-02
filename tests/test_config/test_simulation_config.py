# tests/test_config/test_simulation_config.py
import pytest
from desk.config.simulation_config import SimulationConfig


class TestSimulationConfig:
    """Test SimulationConfig dataclass."""
    
    def test_config_creation(self):
        """Test creating a simulation configuration."""
        config = SimulationConfig(
            duration=1000,
            warm_up_period=100,
            seed=123,
            check_stability=True
        )
        
        assert config.duration == 1000
        assert config.warm_up_period == 100
        assert config.seed == 123
        assert config.check_stability is True
    
    def test_config_default_values(self):
        """Test default configuration values."""
        config = SimulationConfig(duration=500)
        
        assert config.warm_up_period == 0.0
        assert config.seed is None
        assert config.check_stability is False
    
    def test_validate_valid_config(self):
        """Test validation of valid configuration."""
        config = SimulationConfig(
            duration=1000,
            warm_up_period=100
        )
        
        # Should not raise any exception
        config.validate()
    
    def test_validate_negative_duration(self):
        """Test validation fails for negative duration."""
        config = SimulationConfig(duration=-100)
        
        with pytest.raises(ValueError, match="Duration must be positive"):
            config.validate()
    
    def test_validate_zero_duration(self):
        """Test validation fails for zero duration."""
        config = SimulationConfig(duration=0)
        
        with pytest.raises(ValueError, match="Duration must be positive"):
            config.validate()
    
    def test_validate_negative_warm_up(self):
        """Test validation fails for negative warm-up period."""
        config = SimulationConfig(
            duration=1000,
            warm_up_period=-50
        )
        
        with pytest.raises(ValueError, match="Warm-up period cannot be negative"):
            config.validate()
    
    def test_validate_warm_up_exceeds_duration(self):
        """Test validation fails when warm-up >= duration."""
        config = SimulationConfig(
            duration=100,
            warm_up_period=150
        )
        
        with pytest.raises(ValueError, match="Warm-up period must be less than duration"):
            config.validate()
    
    def test_validate_warm_up_equals_duration(self):
        """Test validation fails when warm-up equals duration."""
        config = SimulationConfig(
            duration=100,
            warm_up_period=100
        )
        
        with pytest.raises(ValueError, match="Warm-up period must be less than duration"):
            config.validate()