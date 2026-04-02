# tests/test_blocks/test_decide_block.py
import pytest
import simpy
from desk.blocks.decide_block import DecideBlock
from desk.blocks.dispose_block import DisposeBlock
from desk.core.entity import Entity, EventLogger


class TestDecideBlock:
    """Test DecideBlock functionality."""
    
    def test_decide_block_initialization(self, env_with_model):
        """Test DecideBlock initialization."""
        env = env_with_model
        
        block = DecideBlock("Decision", env, decision_type="probability")
        
        assert block.name == "Decision"
        assert block.decision_type == "probability"
        assert block.routes == {}
        assert block.decision_counts == {}
    
    def test_add_route_probability(self, env_with_model):
        """Test adding probability-based route."""
        env = env_with_model
        block = DecideBlock("Decision", env, decision_type="probability")
        next_block = DisposeBlock("Exit", env)
        
        block.add_route("route1", next_block, probability=0.7)
        
        assert "route1" in block.routes
        assert block.routes["route1"]["probability"] == 0.7
        assert block.routes["route1"]["block"] == next_block
    
    def test_add_route_condition(self, env_with_model):
        """Test adding condition-based route."""
        env = env_with_model
        block = DecideBlock("Decision", env, decision_type="condition")
        next_block = DisposeBlock("Exit", env)
        
        condition = lambda e: e.priority < 2
        block.add_route("urgent", next_block, condition=condition)
        
        assert "urgent" in block.routes
        assert block.routes["urgent"]["condition"] == condition
    
    def test_probability_routing(self, env_with_model):
        """Test probability-based routing."""
        env = env_with_model
        decision = DecideBlock("Decision", env, decision_type="probability")
        
        exit1 = DisposeBlock("Exit1", env)
        exit2 = DisposeBlock("Exit2", env)
        
        decision.add_route("route1", exit1, probability=0.5)
        decision.add_route("route2", exit2, probability=0.5)
        
        # Process multiple entities to test distribution
        entities_to_route1 = 0
        entities_to_route2 = 0
        
        for i in range(100):
            entity = Entity(f"E{i}", 0)
            
            def run_test(ent):
                yield from decision.process_entity(ent)
            
            env.process(run_test(entity))
        
        env.run()
        
        # Check that both routes were used
        assert decision.decision_counts["route1"] > 0
        assert decision.decision_counts["route2"] > 0
        assert decision.decision_counts["route1"] + decision.decision_counts["route2"] == 100
    
    def test_condition_routing(self, env_with_model):
        """Test condition-based routing."""
        env = env_with_model
        decision = DecideBlock("Decision", env, decision_type="condition")
        
        urgent_exit = DisposeBlock("UrgentExit", env)
        normal_exit = DisposeBlock("NormalExit", env)
        
        decision.add_route(
            "urgent",
            urgent_exit,
            condition=lambda e: e.priority <= 1
        )
        decision.add_route(
            "normal",
            normal_exit,
            condition=lambda e: e.priority > 1
        )
        
        # Test urgent entity
        urgent_entity = Entity("E1", 0, priority=0)
        
        def run_urgent():
            yield from decision.process_entity(urgent_entity)
        
        env.process(run_urgent())
        env.run()
        
        assert decision.decision_counts["urgent"] == 1
        assert urgent_entity.get_attribute("Decision_decision") == "urgent"
        
        # Test normal entity
        env = env_with_model
        decision = DecideBlock("Decision", env, decision_type="condition")
        decision.add_route("urgent", urgent_exit, condition=lambda e: e.priority <= 1)
        decision.add_route("normal", normal_exit, condition=lambda e: e.priority > 1)
        
        normal_entity = Entity("E2", 0, priority=3)
        
        def run_normal():
            yield from decision.process_entity(normal_entity)
        
        env.process(run_normal())
        env.run()
        
        assert decision.decision_counts["normal"] == 1
    
    def test_event_logging(self, env_with_model):
        """Test that decisions are logged."""
        env = env_with_model
        logger = EventLogger()
        decision = DecideBlock("Decision", env, decision_type="probability", event_logger=logger)
        
        exit_block = DisposeBlock("Exit", env)
        decision.add_route("route1", exit_block, probability=1.0)
        
        entity = Entity("E1", 0)
        
        def run_test():
            yield from decision.process_entity(entity)
        
        env.process(run_test())
        env.run()
        
        events = logger.get_dataframe()
        decision_events = events[events["activity"].str.contains("Decision")]
        
        assert len(decision_events) >= 1
        assert "route1" in decision_events.iloc[0]["activity"]