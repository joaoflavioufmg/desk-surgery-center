# tests/test_analytics/test_financial.py
import pytest
import simpy
from desk.analytics.financial import FinancialAnalyzer
from desk.core.simulation_model import SimulationModel
from desk.blocks.dispose_block import DisposeBlock
from desk.core.entity import Entity


class TestFinancialAnalyzer:
    """Test FinancialAnalyzer functionality."""
    
    def test_financial_analyzer_initialization(self):
        """Test creating financial analyzer."""
        model = SimulationModel()
        analyzer = FinancialAnalyzer(model)
        
        assert analyzer.model == model
    
    def test_get_financial_summary_empty(self):
        """Test financial summary with no entities."""
        model = SimulationModel()
        dispose = DisposeBlock("Exit", model.env)
        model.add_block(dispose)
        
        analyzer = FinancialAnalyzer(model)
        summary = analyzer.get_financial_summary()
        
        assert summary['total_revenue'] == 0
        assert summary['total_costs'] == 0
        assert summary['net_profit'] == 0
        assert summary['num_entities'] == 0
    
    def test_get_financial_summary_with_data(self):
        """Test financial calculations."""
        model = SimulationModel()
        dispose = DisposeBlock("Exit", model.env)
        model.add_block(dispose)
        
        # Create entities with financial attributes
        entity1 = Entity("E1", creation_time=0)
        entity1.add_attribute("disposal_time", 10.0)
        entity1.add_attribute("Exit_revenue", 250.0)
        entity1.add_attribute("Service_cost", 100.0)
        entity1.add_attribute("Pharmacy_cost", 30.0)
        
        entity2 = Entity("E2", creation_time=0)
        entity2.add_attribute("disposal_time", 20.0)
        entity2.add_attribute("Exit_revenue", 300.0)
        entity2.add_attribute("Service_cost", 150.0)
        entity2.add_attribute("Pharmacy_cost", 40.0)
        
        dispose.disposed_entities = [entity1, entity2]
        
        analyzer = FinancialAnalyzer(model)
        summary = analyzer.get_financial_summary()
        
        # Total revenue: 250 + 300 = 550
        assert summary['total_revenue'] == 550.0
        
        # Total costs: (100+30) + (150+40) = 320
        assert summary['total_costs'] == 320.0
        
        # Net profit: 550 - 320 = 230
        assert summary['net_profit'] == 230.0
        
        # Average per entity
        assert summary['avg_revenue_per_entity'] == 275.0  # 550/2
        assert summary['avg_cost_per_entity'] == 160.0  # 320/2
        assert summary['avg_profit_per_entity'] == 115.0  # 230/2
    
    def test_costs_by_activity(self):
        """Test cost breakdown by activity."""
        model = SimulationModel()
        dispose = DisposeBlock("Exit", model.env)
        model.add_block(dispose)
        
        entity1 = Entity("E1", creation_time=0)
        entity1.add_attribute("disposal_time", 10.0)
        entity1.add_attribute("Triage_cost", 20.0)
        entity1.add_attribute("Service_cost", 100.0)
        
        entity2 = Entity("E2", creation_time=0)
        entity2.add_attribute("disposal_time", 20.0)
        entity2.add_attribute("Triage_cost", 25.0)
        entity2.add_attribute("Service_cost", 120.0)
        
        dispose.disposed_entities = [entity1, entity2]
        
        analyzer = FinancialAnalyzer(model)
        summary = analyzer.get_financial_summary()
        
        costs_by_activity = summary['costs_by_activity']
        
        assert 'Triage' in costs_by_activity
        assert costs_by_activity['Triage'] == 45.0  # 20 + 25
        
        assert 'Service' in costs_by_activity
        assert costs_by_activity['Service'] == 220.0  # 100 + 120
    
    def test_warm_up_handling(self):
        """Test that warm-up period is respected."""
        model = SimulationModel()
        model.warm_up_period = 50.0
        dispose = DisposeBlock("Exit", model.env)
        model.add_block(dispose)
        
        # Entity during warm-up (should be excluded)
        entity1 = Entity("E1", creation_time=0)
        entity1.add_attribute("disposal_time", 30.0)
        entity1.add_attribute("Exit_revenue", 100.0)
        
        # Entity after warm-up (should be included)
        entity2 = Entity("E2", creation_time=50.0)
        entity2.add_attribute("disposal_time", 70.0)
        entity2.add_attribute("Exit_revenue", 200.0)
        
        dispose.disposed_entities = [entity1, entity2]
        
        analyzer = FinancialAnalyzer(model)
        summary = analyzer.get_financial_summary()
        
        # Only entity2 should be counted
        assert summary['total_revenue'] == 200.0
        assert summary['num_entities'] == 1