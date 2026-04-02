# tests/test_blocks/test_dispose_block.py
import pytest
import simpy
from desk.blocks.dispose_block import DisposeBlock
from desk.core.entity import Entity, EventLogger


class TestDisposeBlock:
    """Test DisposeBlock functionality."""
    
    def test_dispose_block_initialization(self, env_with_model):
        """Test DisposeBlock initialization."""
        env = env_with_model
        block = DisposeBlock("Exit", env)
        
        assert block.name == "Exit"
        assert block.entities_disposed == 0
        assert block.total_system_time == 0.0
        assert block.disposed_entities == []
    
    def test_entity_disposal(self, env_with_model):
        """Test basic entity disposal."""
        env = env_with_model
        block = DisposeBlock("Exit", env)
        
        entity = Entity("E1", creation_time=10.0)
        env._now = 25.0
        
        def run_test():
            yield from block.process_entity(entity)
        
        env.process(run_test())
        env.run()
        
        assert block.entities_disposed == 1
        assert len(block.disposed_entities) == 1
        assert entity.get_attribute("system_time") == 15.0
        assert entity.get_attribute("disposal_time") == 25.0
    
    def test_multiple_disposals(self, env_with_model):
        """Test disposing multiple entities."""
        env = env_with_model
        block = DisposeBlock("Exit", env)
        
        entities = [
            Entity("E1", creation_time=0.0),
            Entity("E2", creation_time=5.0),
            Entity("E3", creation_time=10.0)
        ]
        
        def dispose_entity(ent, time):
            yield env.timeout(time)
            yield from block.process_entity(ent)
        
        for i, ent in enumerate(entities):
            env.process(dispose_entity(ent, 20.0 + i * 5))
        
        env.run()
        
        assert block.entities_disposed == 3
        assert len(block.disposed_entities) == 3
    
    def test_warm_up_handling(self, env_with_model):
        """Test that warm-up period is respected."""
        env = env_with_model
        env.warm_up_period = 50.0
        block = DisposeBlock("Exit", env)
        
        # Entity disposed during warm-up
        entity1 = Entity("E1", creation_time=10.0)
        env._now = 30.0
        
        def dispose1():
            yield from block.process_entity(entity1)
        
        env.process(dispose1())
        env.run(until=30.1)
        
        # Entity disposed after warm-up
        entity2 = Entity("E2", creation_time=55.0)
        env._now = 70.0
        
        def dispose2():
            yield from block.process_entity(entity2)
        
        env.process(dispose2())
        env.run()
        
        # Only entity2 should count in statistics
        assert block.entities_disposed == 1
        assert len(block.disposed_entities) == 2  # Both kept for plotting
    
    def test_average_system_time(self, env_with_model):
        """Test average system time calculation."""
        env = env_with_model
        block = DisposeBlock("Exit", env)
        
        # Create entities with known system times
        entity1 = Entity("E1", creation_time=0.0)
        entity2 = Entity("E2", creation_time=0.0)
        entity3 = Entity("E3", creation_time=0.0)
        
        def dispose_at_time(ent, time):
            env._now = time
            yield from block.process_entity(ent)
        
        env.process(dispose_at_time(entity1, 10.0))  # System time: 10
        env.process(dispose_at_time(entity2, 20.0))  # System time: 20
        env.process(dispose_at_time(entity3, 30.0))  # System time: 30
        
        env.run()
        
        # Average: (10 + 20 + 30) / 3 = 20
        assert block.get_average_system_time() == 20.0
    
    def test_event_logging(self, env_with_model):
        """Test that disposal events are logged."""
        env = env_with_model
        logger = EventLogger()
        block = DisposeBlock("Exit", env, event_logger=logger)
        
        entity = Entity("E1", creation_time=5.0)
        env._now = 15.0
        
        def run_test():
            yield from block.process_entity(entity)
        
        env.process(run_test())
        env.run()
        
        events = logger.get_dataframe()
        assert len(events) == 1
        assert events.iloc[0]["activity"] == "Discharge"
        assert events.iloc[0]["lifecycle"] == "complete"
        assert events.iloc[0]["system_time"] == 10.0
    
    def test_attribute_assignment(self, env_with_model):
        """Test that configured attributes are applied."""
        env = env_with_model
        block = DisposeBlock("Exit", env)
        
        block.assign_attributes(
            revenue=lambda: 250,
            satisfaction_score=5
        )
        
        entity = Entity("E1", creation_time=0.0)
        env._now = 10.0
        
        def run_test():
            yield from block.process_entity(entity)
        
        env.process(run_test())
        env.run()
        
        assert entity.get_attribute("Exit_revenue") == 250
        assert entity.get_attribute("Exit_satisfaction_score") == 5