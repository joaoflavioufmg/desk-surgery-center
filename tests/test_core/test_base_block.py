# tests/test_core/test_base_block.py
import pytest
import simpy
from desk.core.base_block import BaseBlock
from desk.core.entity import Entity, EventLogger


class ConcreteBlock(BaseBlock):
    """Concrete implementation for testing abstract BaseBlock."""
    
    def process_entity(self, entity: Entity):
        """Minimal implementation."""
        entity.route_history.append(self.name)
        yield self.env.timeout(0)


class TestBaseBlock:
    """Test BaseBlock abstract class functionality."""

    @pytest.fixture
    def env(self):
        """Create environment with model attribute."""
        env = simpy.Environment()
        # Add mock model to prevent AttributeError
        class MockModel:
            event_tracer = None
        env.model = MockModel()
        return env

    def test_base_block_creation(self, env):
        """Test creating a concrete block."""
        block = ConcreteBlock("TestBlock", env)
        
        assert block.name == "TestBlock"
        assert block.env == env
        assert block.next_block is None
        assert block.statistics == {}
        assert block.attributes_to_assign == {}
        assert block.attributes_to_modify == {}
        assert block.activity_priority is None

    def test_base_block_with_event_logger(self, env):
        """Test creating block with event logger."""
        logger = EventLogger()
        block = ConcreteBlock("TestBlock", env, event_logger=logger)
        
        assert block.event_logger == logger

    def test_connect_to(self, env):
        """Test connecting blocks."""
        block1 = ConcreteBlock("Block1", env)
        block2 = ConcreteBlock("Block2", env)
        
        block1.connect_to(block2)
        
        assert block1.next_block == block2

    def test_assign_attributes_fixed_values(self, env):
        """Test assigning fixed attribute values."""
        block = ConcreteBlock("TestBlock", env)
        
        block.assign_attributes(
            cost=100,
            category="outpatient",
            priority=1
        )
        
        assert block.attributes_to_assign["cost"] == 100
        assert block.attributes_to_assign["category"] == "outpatient"
        assert block.attributes_to_assign["priority"] == 1

    def test_assign_attributes_callable(self, env):
        """Test assigning callable attribute values."""
        block = ConcreteBlock("TestBlock", env)
        
        block.assign_attributes(
            cost=lambda: 150,
            revenue=lambda: 200
        )
        
        assert callable(block.attributes_to_assign["cost"])
        assert callable(block.attributes_to_assign["revenue"])

    def test_apply_attributes_fixed(self, env):
        """Test applying fixed attributes to entity."""
        block = ConcreteBlock("TestBlock", env)
        entity = Entity("E1", 0)
        
        block.assign_attributes(cost=100, category="urgent")
        assigned_attrs = block._apply_attributes(entity)
        
        # Check both unprefixed and prefixed attributes are set
        assert entity.get_attribute("cost") == 100
        assert entity.get_attribute("category") == "urgent"
        assert entity.get_attribute("TestBlock_cost") == 100
        assert entity.get_attribute("TestBlock_category") == "urgent"
        
        # Check return value
        assert isinstance(assigned_attrs, list)
        assert len(assigned_attrs) == 2
        assert ("cost", 100) in assigned_attrs
        assert ("category", "urgent") in assigned_attrs

    def test_apply_attributes_callable(self, env):
        """Test applying callable attributes to entity."""
        block = ConcreteBlock("TestBlock", env)
        entity = Entity("E1", 0)
        
        call_count = 0
        def get_cost():
            nonlocal call_count
            call_count += 1
            return 100 + call_count
        
        block.assign_attributes(cost=get_cost)
        
        # Apply twice to verify callable is executed each time
        assigned_attrs1 = block._apply_attributes(entity)
        assert entity.get_attribute("cost") == 101
        assert entity.get_attribute("TestBlock_cost") == 101
        assert assigned_attrs1 == [("cost", 101)]
        
        assigned_attrs2 = block._apply_attributes(entity)
        assert entity.get_attribute("cost") == 102
        assert entity.get_attribute("TestBlock_cost") == 102
        assert assigned_attrs2 == [("cost", 102)]

    def test_modify_attributes(self, env):
        """Test modifying entity attributes."""
        block = ConcreteBlock("TestBlock", env)
        entity = Entity("E1", 0)
        
        # Set initial value
        entity.add_attribute("sede", 5)
        
        # Configure modification
        block.modify_attributes(sede=lambda current: current - 1)
        
        # Apply modification
        modified_attrs = block._modify_attributes(entity)
        
        # Check modified value
        assert entity.get_attribute("sede") == 4
        
        # Check return value
        assert isinstance(modified_attrs, list)
        assert len(modified_attrs) == 1
        assert modified_attrs[0] == ("sede", 5, 4)  # (name, old_value, new_value)

    def test_modify_attributes_with_default(self, env):
        """Test modifying attributes with default values."""
        block = ConcreteBlock("TestBlock", env)
        entity = Entity("E1", 0)
        
        # Don't set initial value - should use default of 0
        block.modify_attributes(counter=lambda current: current + 10)
        
        modified_attrs = block._modify_attributes(entity)
        
        assert entity.get_attribute("counter") == 10
        assert modified_attrs == [("counter", 0, 10)]

    def test_set_activity_priority(self, env):
        """Test setting activity priority."""
        block = ConcreteBlock("TestBlock", env)
        
        block.set_activity_priority(5)
        
        assert block.activity_priority == 5

    def test_update_statistics(self, env):
        """Test updating block statistics."""
        block = ConcreteBlock("TestBlock", env)
        
        block.update_statistics("processed", 10)
        block.update_statistics("avg_time", 5.5)
        
        assert block.statistics["processed"] == 10
        assert block.statistics["avg_time"] == 5.5

    def test_log_start_with_activity_priority(self, env):
        """Test logging activity start with activity priority."""
        logger = EventLogger()
        block = ConcreteBlock("TestBlock", env, event_logger=logger)
        block.set_activity_priority(3)
        entity = Entity("E1", 0, priority=2)
        
        block.log_start(entity, "Resource1")
        
        assert len(logger.events) == 1
        event = logger.events[0]
        assert event["case_id"] == "E1"
        assert event["activity"] == "TestBlock"
        assert event["lifecycle"] == "start"
        assert event["resource"] == "Resource1"
        assert event["priority"] == 2
        assert event["activity_priority"] == 3

    def test_log_complete(self, env):
        """Test logging activity completion."""
        logger = EventLogger()
        block = ConcreteBlock("TestBlock", env, event_logger=logger)
        entity = Entity("E1", 0, priority=1)
        
        block.log_complete(entity, "Resource1")
        
        assert len(logger.events) == 1
        event = logger.events[0]
        assert event["lifecycle"] == "complete"
        assert event["case_id"] == "E1"
        assert event["activity"] == "TestBlock"

    def test_send_to_next(self, env):
        """Test sending entity to next block."""
        block1 = ConcreteBlock("Block1", env)
        block2 = ConcreteBlock("Block2", env)
        block1.connect_to(block2)
        
        entity = Entity("E1", 0)
        
        def run_test():
            yield from block1.send_to_next(entity)
        
        env.process(run_test())
        env.run()
        
        assert "Block2" in entity.route_history

    def test_send_to_next_no_connection(self, env):
        """Test sending entity when no next block exists."""
        block = ConcreteBlock("Block1", env)
        entity = Entity("E1", 0)
        
        def run_test():
            yield from block.send_to_next(entity)
        
        env.process(run_test())
        env.run()  # Should complete without error
        
        # Entity should not have any additional route history
        assert len(entity.route_history) == 0

    def test_tracer_integration(self):
        """Test that tracer is accessible from block."""
        env = simpy.Environment()
        
        # Create a mock model with tracer
        class MockModel:
            def __init__(self):
                self.event_tracer = None
        
        env.model = MockModel()
        block = ConcreteBlock("TestBlock", env)
        
        # Tracer should be None initially
        assert block.tracer is None
        
        # Set tracer on model
        class MockTracer:
            pass
        
        env.model.event_tracer = MockTracer()
        
        # Create new block - should pick up tracer
        block2 = ConcreteBlock("TestBlock2", env)
        assert block2.tracer is not None
        assert isinstance(block2.tracer, MockTracer)