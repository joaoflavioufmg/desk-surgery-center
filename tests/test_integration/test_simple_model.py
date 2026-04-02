# tests/test_integration/test_simple_model.py
import pytest
import simpy
import random
from desk.core.simulation_model import SimulationModel
from desk.blocks.create_block import CreateBlock
from desk.blocks.process_block import ProcessBlock
from desk.blocks.dispose_block import DisposeBlock
from desk.core.entity import EventLogger
from desk.analytics.metrics import MetricsCollector
from desk.analytics.reporting import SimulationReporter


class TestSimpleModelIntegration:
    """Integration tests with a simple queue model."""
    
    def test_simple_queue_model(self):
        """Test a complete simple queue model."""
        # Create model
        model = SimulationModel()
        logger = EventLogger()
        
        # Add resource
        resource = model.add_resource("server", capacity=1)
        
        # Create blocks
        arrivals = CreateBlock(
            "Arrivals",
            model.env,
            inter_arrival_time=lambda: 5.0,
            max_arrivals=10,
            event_logger=logger
        )
        
        service = ProcessBlock(
            "Service",
            model.env,
            resource=resource,
            delay_time=lambda: 3.0
        )
        
        exit_block = DisposeBlock("Exit", model.env)
        
        model.add_block(arrivals)
        model.add_block(service)
        model.add_block(exit_block)
        
        model.connect_blocks("Arrivals", "Service")
        model.connect_blocks("Service", "Exit")
        
        # Run with warm-up
        model.run_simulation(until=200, warm_up_period=50, seed=123)
        
        # Statistics should only count post-warm-up
        assert model.warm_up_period == 50
        assert exit_block.entities_disposed < len(exit_block.disposed_entities)
    
    def test_model_with_decision(self):
        """Test model with decision routing."""
        from desk.blocks.decide_block import DecideBlock
        
        model = SimulationModel()
        
        arrivals = CreateBlock(
            "Arrivals",
            model.env,
            inter_arrival_time=lambda: 5.0,
            max_arrivals=20,
            priority_generator=lambda: 0 if random.random() < 0.3 else 1
        )
        
        decision = DecideBlock(
            "Priority_Check",
            model.env,
            decision_type="condition"
        )
        
        urgent_exit = DisposeBlock("Urgent_Exit", model.env)
        normal_exit = DisposeBlock("Normal_Exit", model.env)
        
        decision.add_route(
            "urgent",
            urgent_exit,
            condition=lambda e: e.priority == 0
        )
        decision.add_route(
            "normal",
            normal_exit,
            condition=lambda e: e.priority == 1
        )
        
        model.add_block(arrivals)
        model.add_block(decision)
        model.add_block(urgent_exit)
        model.add_block(normal_exit)
        
        model.connect_blocks("Arrivals", "Priority_Check")
        
        # Run simulation
        model.run_simulation(until=150, seed=123)
        
        # Both exits should have entities
        total_disposed = urgent_exit.entities_disposed + normal_exit.entities_disposed
        assert total_disposed > 0
        assert decision.decision_counts["urgent"] + decision.decision_counts["normal"] == total_disposed
    
    def test_metrics_collection(self):
        """Test metrics collection from completed simulation."""
        model = SimulationModel()
        
        resource = model.add_resource("server", capacity=2)
        
        arrivals = CreateBlock(
            "Arrivals",
            model.env,
            inter_arrival_time=lambda: 5.0,
            max_arrivals=20
        )
        
        service = ProcessBlock(
            "Service",
            model.env,
            resource=resource,
            delay_time=lambda: 3.0
        )
        
        exit_block = DisposeBlock("Exit", model.env)
        
        model.add_block(arrivals)
        model.add_block(service)
        model.add_block(exit_block)
        
        model.connect_blocks("Arrivals", "Service")
        model.connect_blocks("Service", "Exit")
        
        model.run_simulation(until=150, seed=123)
        
        # Collect metrics
        metrics = MetricsCollector(model)
        
        entity_metrics = metrics.get_entity_metrics_summary()
        assert entity_metrics['tempo_medio_sistema'] > 0
        
        resource_metrics = metrics.get_resource_metrics_summary()
        assert 'server' in resource_metrics
        assert 0 <= resource_metrics['server']['taxa_utilizacao'] <= 1
    
    def test_financial_attributes(self):
        """Test financial attribute assignment."""
        from desk.analytics.financial import FinancialAnalyzer
        
        model = SimulationModel()
        
        resource = model.add_resource("server", capacity=1)
        
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
            delay_time=lambda: 3.0
        )
        service.assign_attributes(cost=lambda: 50.0)
        
        exit_block = DisposeBlock("Exit", model.env)
        exit_block.assign_attributes(revenue=lambda: 100.0)
        
        model.add_block(arrivals)
        model.add_block(service)
        model.add_block(exit_block)
        
        model.connect_blocks("Arrivals", "Service")
        model.connect_blocks("Service", "Exit")
        
        model.run_simulation(until=100, seed=123)
        
        # Analyze financials
        analyzer = FinancialAnalyzer(model)
        summary = analyzer.get_financial_summary()
        
        assert summary['total_revenue'] > 0
        assert summary['total_costs'] > 0
        assert summary['net_profit'] != 0