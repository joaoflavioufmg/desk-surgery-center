# tests/test_analytics/test_metrics.py
import pytest
import simpy
import math
from desk.analytics.metrics import MetricsCollector
from desk.core.simulation_model import SimulationModel
from desk.blocks.create_block import CreateBlock
from desk.blocks.process_block import ProcessBlock
from desk.blocks.dispose_block import DisposeBlock
from desk.core.entity import Entity


class TestMetricsCollector:
    """Test MetricsCollector functionality."""
    
    def test_metrics_collector_initialization(self):
        """Test creating metrics collector."""
        model = SimulationModel()
        metrics = MetricsCollector(model)
        
        assert metrics.model == model
    
    def test_get_entity_metrics_empty(self):
        """Test metrics with no disposed entities."""
        model = SimulationModel()
        dispose = DisposeBlock("Exit", model.env)
        model.add_block(dispose)
        
        metrics = MetricsCollector(model)
        summary = metrics.get_entity_metrics_summary()
        
        assert summary['tempo_medio_sistema'] == 0
        assert summary['atividades'] == {}
    
    def test_get_entity_metrics_with_entities(self):
        """Test entity metrics calculation."""
        model = SimulationModel()
        dispose = DisposeBlock("Exit", model.env)
        model.add_block(dispose)
        
        # Create mock entities
        entity1 = Entity("E1", creation_time=0)
        entity1.add_attribute("system_time", 10.0)
        entity1.add_attribute("disposal_time", 10.0)
        entity1.add_attribute("Service_queue_time", 2.0)
        entity1.add_attribute("Service_service_time", 8.0)
        
        entity2 = Entity("E2", creation_time=0)
        entity2.add_attribute("system_time", 20.0)
        entity2.add_attribute("disposal_time", 20.0)
        entity2.add_attribute("Service_queue_time", 5.0)
        entity2.add_attribute("Service_service_time", 15.0)
        
        dispose.disposed_entities = [entity1, entity2]
        
        metrics = MetricsCollector(model)
        summary = metrics.get_entity_metrics_summary()
        
        # Average system time: (10 + 20) / 2 = 15
        assert summary['tempo_medio_sistema'] == 15.0
        
        # Check activity metrics
        assert 'Service' in summary['atividades']
        assert summary['atividades']['Service']['tempo_medio_fila'] == 3.5  # (2+5)/2
        assert summary['atividades']['Service']['tempo_medio_atendimento'] == 11.5  # (8+15)/2
    
    def test_get_entity_metrics_with_warm_up(self):
        """Test that warm-up period is respected."""
        model = SimulationModel()
        model.warm_up_period = 50.0
        dispose = DisposeBlock("Exit", model.env)
        model.add_block(dispose)
        
        # Entity during warm-up (should be excluded)
        entity1 = Entity("E1", creation_time=0)
        entity1.add_attribute("system_time", 10.0)
        entity1.add_attribute("disposal_time", 30.0)  # Before warm-up end
        
        # Entity after warm-up (should be included)
        entity2 = Entity("E2", creation_time=50.0)
        entity2.add_attribute("system_time", 20.0)
        entity2.add_attribute("disposal_time", 70.0)  # After warm-up
        
        dispose.disposed_entities = [entity1, entity2]
        
        metrics = MetricsCollector(model)
        summary = metrics.get_entity_metrics_summary()
        
        # Only entity2 should be counted
        assert summary['tempo_medio_sistema'] == 20.0
    
    def test_get_resource_metrics_empty(self):
        """Test resource metrics with no data."""
        model = SimulationModel()
        model.add_resource("service", capacity=2)
        
        metrics = MetricsCollector(model)
        summary = metrics.get_resource_metrics_summary()
        
        assert summary == {}
    
    def test_get_resource_metrics_with_data(self):
        """Test resource metrics calculation."""
        model = SimulationModel()
        model.env._now = 100.0
        
        resource = model.add_resource("service", capacity=2)
        process = ProcessBlock(
            "Service",
            model.env,
            resource=resource,
            delay_time=lambda: 1.0
        )
        model.add_block(process)
        
        # Add mock resource data: (time, in_service, queue_length)
        process.resource_data = [
            (0, 0, 0),
            (10, 1, 0),
            (20, 2, 1),
            (50, 1, 0),
            (100, 0, 0)
        ]
        process.max_queue_length = 1
        process.max_in_service = 2
        
        metrics = MetricsCollector(model)
        summary = metrics.get_resource_metrics_summary()
        
        assert "service" in summary
        assert summary["service"]["taxa_utilizacao"] > 0
        assert summary["service"]["maximo_fila"] == 1
        assert summary["service"]["maximo_atendimento"] == 2
    
    def test_handle_nan_values(self):
        """Test that NaN values are handled correctly."""
        model = SimulationModel()
        dispose = DisposeBlock("Exit", model.env)
        model.add_block(dispose)
        
        entity = Entity("E1", creation_time=0)
        entity.add_attribute("system_time", 10.0)
        entity.add_attribute("disposal_time", 10.0)
        entity.add_attribute("Service_queue_time", float('nan'))  # NaN value
        
        dispose.disposed_entities = [entity]
        
        metrics = MetricsCollector(model)
        summary = metrics.get_entity_metrics_summary()
        
        # Should not crash and should skip NaN values
        assert not math.isnan(summary['tempo_medio_sistema'])