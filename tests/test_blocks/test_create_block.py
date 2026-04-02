# tests/test_blocks/test_create_block.py
import pytest
import simpy
from desk.blocks.create_block import CreateBlock
from desk.core.entity import Entity, EventLogger


class TestCreateBlock:
    """Test CreateBlock functionality."""
    
    # def test_create_block_initialization(self):
    #     """Test basic CreateBlock initialization."""
    #     env = simpy.Environment()
    def test_create_block_initialization(self, env_with_model):
        """Test basic CreateBlock initialization."""
        env = env_with_model
        
        block = CreateBlock(
            "Arrivals",
            env,
            inter_arrival_time=lambda: 5.0,
            entity_prefix="Patient",
            max_arrivals=100,
            first_creation=10.0
        )
        
        assert block.name == "Arrivals"
        assert block.env == env
        assert block.entity_prefix == "Patient"
        assert block.max_arrivals == 100
        assert block.first_creation == 10.0
        assert block.entities_created >= 0
    
    def test_create_with_priority_generator(self, env_with_model):
        """Test CreateBlock with priority generator."""
        # env = simpy.Environment()
        env = env_with_model
        
        priority_gen = lambda: 1
        block = CreateBlock(
            "Arrivals",
            env,
            inter_arrival_time=lambda: 1.0,
            priority_generator=priority_gen
        )
        
        assert block.priority_generator == priority_gen
    
    def test_entity_generation_count(self, env_with_model):
        """Test that entities are created correctly."""
        # env = simpy.Environment()
        env = env_with_model
        
        block = CreateBlock(
            "Arrivals",
            env,
            inter_arrival_time=lambda: 1.0,
            max_arrivals=5
        )
        
        block.start_generation()
        env.run()
        
        assert block.entities_created >= block.max_arrivals
    
    def test_entity_generation_with_first_creation_delay(self, env_with_model):
        """Test first_creation delay."""
        # env = simpy.Environment()
        env = env_with_model
        
        block = CreateBlock(
            "Arrivals",
            env,
            inter_arrival_time=lambda: 1.0,
            max_arrivals=3,
            first_creation=5.0
        )
        
        block.start_generation()
        env.run()
        
        # First entity created at t=5, then t=6, t=7
        assert env.now >= 7.0
    
    def test_entity_id_format(self, env_with_model):
        """Test entity ID formatting."""
        # env = simpy.Environment()
        env = env_with_model
        logger = EventLogger()
        
        block = CreateBlock(
            "Arrivals",
            env,
            inter_arrival_time=lambda: 1.0,
            entity_prefix="Customer",
            max_arrivals=3,
            event_logger=logger
        )
        
        block.start_generation()
        env.run()
        
        events = logger.get_dataframe()
        case_ids = events["case_id"].unique()
        
        # assert "Customer_0" in case_ids
        # assert "Customer_1" in case_ids
        # assert "Customer_2" in case_ids
        assert len(case_ids) == 3
        assert all(cid.startswith("Customer_") for cid in case_ids)

    
    def test_priority_assignment(self, env_with_model):
        """Test priority is assigned to entities."""
        # env = simpy.Environment()
        env = env_with_model
        logger = EventLogger()
        
        priority_values = [0, 1, 2]
        priority_iter = iter(priority_values)
        
        block = CreateBlock(
            "Arrivals",
            env,
            inter_arrival_time=lambda: 1.0,
            max_arrivals=3,
            priority_generator=lambda: next(priority_iter),
            event_logger=logger
        )
        
        block.start_generation()
        env.run()
        
        events = logger.get_dataframe()
        priorities = events["priority"].tolist()
        
        assert priorities == priority_values
    
    def test_event_logging(self, env_with_model):
        """Test that arrivals are logged."""
        # env = simpy.Environment()
        env = env_with_model
        logger = EventLogger()
        
        block = CreateBlock(
            "Arrivals",
            env,
            inter_arrival_time=lambda: 2.0,
            max_arrivals=2,
            event_logger=logger
        )
        
        block.start_generation()
        env.run()
        
        events = logger.get_dataframe()
        
        assert len(events) == 2
        assert all(events["activity"] == "Arrival")
        assert all(events["lifecycle"] == "complete")
    
    def test_process_entity_raises_error(self, env_with_model):
        """Test that process_entity raises NotImplementedError."""
        # env = simpy.Environment()
        env = env_with_model
        block = CreateBlock(
            "Arrivals",
            env,
            inter_arrival_time=lambda: 1.0
        )
        
        entity = Entity("E1", 0)
        
        with pytest.raises(NotImplementedError):
            list(block.process_entity(entity))