# tests/test_blocks/test_process_block.py
import pytest
import simpy
from desk.blocks.process_block import ProcessBlock
from desk.core.entity import Entity, EventLogger


class TestProcessBlock:
    """Test ProcessBlock functionality."""
    

    @pytest.fixture
    def env(self):
        """Create environment with model attribute."""
        env = simpy.Environment()
        # Add mock model to prevent AttributeError
        class MockModel:
            event_tracer = None
        env.model = MockModel()
        return env

    def test_process_block_initialization(self, env):
        """Test ProcessBlock initialization."""
        resource = simpy.Resource(env, capacity=2)
        
        block = ProcessBlock(
            "Service",
            env,
            resource=resource,
            delay_time=lambda: 5.0,
            resource_units=1
        )
        
        assert block.name == "Service"
        assert block.resource == resource
        assert block.resource_units == 1
        assert block.entities_processed == 0

    def test_entity_processing(self, env):
        """Test basic entity processing."""
        resource = simpy.Resource(env, capacity=1)
        
        block = ProcessBlock(
            "Service",
            env,
            resource=resource,
            delay_time=lambda: 3.0
        )
        
        entity = Entity("E1", 0)
        
        def run_test():
            yield from block.process_entity(entity)
        
        env.process(run_test())
        env.run()
        
        assert block.entities_processed == 1
        assert entity.get_attribute("Service_service_time") == 3.0
        assert "Service" in entity.route_history

    def test_queue_time_recording(self, env):
        """Test that queue time is recorded."""
        resource = simpy.Resource(env, capacity=1)
        
        block = ProcessBlock(
            "Service",
            env,
            resource=resource,
            delay_time=lambda: 2.0
        )
        
        entity1 = Entity("E1", 0)
        entity2 = Entity("E2", 0)
        
        def process1():
            yield from block.process_entity(entity1)
        
        def process2():
            yield env.timeout(0.5)  # Start slightly after entity1
            yield from block.process_entity(entity2)
        
        env.process(process1())
        env.process(process2())
        env.run()
        
        # Entity2 should have queue time
        queue_time_e2 = entity2.get_attribute("Service_queue_time")
        assert queue_time_e2 > 0

    def test_resource_monitoring(self, env):
        """Test that resource data is collected."""
        resource = simpy.Resource(env, capacity=2)
        
        block = ProcessBlock(
            "Service",
            env,
            resource=resource,
            delay_time=lambda: 1.0
        )
        
        entity = Entity("E1", 0)
        
        def run_test():
            yield from block.process_entity(entity)
        
        env.process(run_test())
        env.run()
        
        assert len(block.resource_data) > 0
        assert block.max_in_service >= 0

    def test_multiple_resource_units(self, env):
        """Test processing with multiple resource units."""
        resource = simpy.Resource(env, capacity=5)
        
        block = ProcessBlock(
            "Service",
            env,
            resource=resource,
            delay_time=lambda: 1.0,
            resource_units=3
        )
        
        entity = Entity("E1", 0)
        
        def run_test():
            yield from block.process_entity(entity)
        
        env.process(run_test())
        env.run()
        
        assert block.entities_processed == 1

    def test_event_logging(self, env):
        """Test that events are logged."""
        resource = simpy.Resource(env, capacity=1)
        logger = EventLogger()
        
        block = ProcessBlock(
            "Service",
            env,
            resource=resource,
            delay_time=lambda: 2.0,
            event_logger=logger
        )
        block.set_resource_name("ServiceResource")
        
        entity = Entity("E1", 0)
        
        def run_test():
            yield from block.process_entity(entity)
        
        env.process(run_test())
        env.run()
        
        events = logger.get_dataframe()
        assert len(events) == 2  # start and complete
        assert events.iloc[0]["lifecycle"] == "start"
        assert events.iloc[1]["lifecycle"] == "complete"
        assert all(events["resource"] == "ServiceResource")

    def test_process_without_resource(self, env):
        """Test ProcessBlock in pure delay mode (no resource)."""
        block = ProcessBlock(
            "Delay",
            env,
            resource=None,  # No resource - pure delay
            delay_time=lambda: 2.5
        )
        
        entity = Entity("E1", 0)
        
        def run_test():
            yield from block.process_entity(entity)
        
        env.process(run_test())
        env.run()
        
        assert block.entities_processed == 1
        assert entity.get_attribute("Delay_service_time") == 2.5
        assert entity.get_attribute("Delay_queue_time") == 0.0  # No queue without resource
        assert "Delay" in entity.route_history

    def test_attribute_assignment(self, env):
        """Test that attributes are assigned to entities."""
        resource = simpy.Resource(env, capacity=1)
        
        block = ProcessBlock(
            "Service",
            env,
            resource=resource,
            delay_time=lambda: 1.0
        )
        
        # Assign attributes
        block.assign_attributes(
            cost=50,
            revenue=lambda: 100
        )
        
        entity = Entity("E1", 0)
        
        def run_test():
            yield from block.process_entity(entity)
        
        env.process(run_test())
        env.run()
        
        # Check attributes were assigned
        assert entity.get_attribute("cost") == 50
        assert entity.get_attribute("Service_cost") == 50
        assert entity.get_attribute("revenue") == 100
        assert entity.get_attribute("Service_revenue") == 100

    def test_attribute_modification(self, env):
        """Test that attributes can be modified."""
        resource = simpy.Resource(env, capacity=1)
        
        block = ProcessBlock(
            "Service",
            env,
            resource=resource,
            delay_time=lambda: 1.0
        )
        
        # Set up modification
        block.modify_attributes(counter=lambda current: current + 1)
        
        entity = Entity("E1", 0)
        entity.add_attribute("counter", 5)
        
        def run_test():
            yield from block.process_entity(entity)
        
        env.process(run_test())
        env.run()
        
        # Check attribute was modified
        assert entity.get_attribute("counter") == 6

    def test_activity_priority(self, env):
        """Test setting activity priority."""
        resource = simpy.PriorityResource(env, capacity=1)
        logger = EventLogger()
        
        block = ProcessBlock(
            "Service",
            env,
            resource=resource,
            delay_time=lambda: 1.0,
            event_logger=logger
        )
        
        # Set activity priority
        block.set_activity_priority(5)
        
        entity = Entity("E1", 0, priority=10)
        
        def run_test():
            yield from block.process_entity(entity)
        
        env.process(run_test())
        env.run()
        
        # Check that activity priority was logged
        events = logger.get_dataframe()
        start_event = events[events["lifecycle"] == "start"].iloc[0]
        assert start_event["activity_priority"] == 5
        assert start_event["priority"] == 10  # Entity priority