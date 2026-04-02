# tests/test_core/test_entity.py
import pytest
import pandas as pd
from desk.core.entity import Entity, EventLogger


class TestEntity:
    """Test Entity class functionality."""
    
    def test_entity_creation(self):
        """Test basic entity creation."""
        entity = Entity(
            id="E1",
            creation_time=10.0,
            data={"type": "patient"},
            route_history=["Arrival"],
            priority=2
        )
        
        assert entity.id == "E1"
        assert entity.creation_time == 10.0
        assert entity.data == {"type": "patient"}
        assert entity.route_history == ["Arrival"]
        assert entity.priority == 2
    
    def test_entity_default_values(self):
        """Test entity creation with default values."""
        entity = Entity(id="E2", creation_time=5.0)
        
        assert entity.data == {}
        assert entity.route_history == []
        assert entity.priority == 0
    
    def test_add_attribute(self):
        """Test adding attributes to entity."""
        entity = Entity(id="E1", creation_time=0)
        
        entity.add_attribute("cost", 100)
        entity.add_attribute("service_time", 15.5)
        
        assert entity.data["cost"] == 100
        assert entity.data["service_time"] == 15.5
    
    def test_get_attribute(self):
        """Test retrieving attributes from entity."""
        entity = Entity(id="E1", creation_time=0)
        entity.add_attribute("revenue", 250)
        
        assert entity.get_attribute("revenue") == 250
        assert entity.get_attribute("nonexistent") is None
        assert entity.get_attribute("nonexistent", default=0) == 0
    
    def test_attribute_overwrite(self):
        """Test overwriting existing attributes."""
        entity = Entity(id="E1", creation_time=0)
        
        entity.add_attribute("status", "waiting")
        assert entity.get_attribute("status") == "waiting"
        
        entity.add_attribute("status", "processing")
        assert entity.get_attribute("status") == "processing"


class TestEventLogger:
    """Test EventLogger class functionality."""
    
    def test_event_logger_creation(self):
        """Test creating an event logger."""
        logger = EventLogger()
        assert logger.events == []
    
    def test_log_single_event(self):
        """Test logging a single event."""
        logger = EventLogger()
        
        logger.log_event(
            case_id="C1",
            activity="Triage",
            timestamp=10.5,
            lifecycle="start",
            resource="Nurse1"
        )
        
        assert len(logger.events) == 1
        event = logger.events[0]
        assert event["case_id"] == "C1"
        assert event["activity"] == "Triage"
        assert event["timestamp"] == 10.5
        assert event["lifecycle"] == "start"
        assert event["resource"] == "Nurse1"
    
    def test_log_multiple_events(self):
        """Test logging multiple events."""
        logger = EventLogger()
        
        logger.log_event("C1", "Activity1", 0, "start")
        logger.log_event("C1", "Activity1", 5, "complete")
        logger.log_event("C2", "Activity1", 3, "start")
        
        assert len(logger.events) == 3
    
    def test_log_event_with_custom_attributes(self):
        """Test logging events with additional attributes."""
        logger = EventLogger()
        
        logger.log_event(
            case_id="C1",
            activity="Consultation",
            timestamp=20.0,
            lifecycle="complete",
            resource="Doctor1",
            cost=150,
            priority=2
        )
        
        event = logger.events[0]
        assert event["cost"] == 150
        assert event["priority"] == 2
    
    def test_get_dataframe(self):
        """Test converting events to DataFrame."""
        logger = EventLogger()
        
        logger.log_event("C1", "Activity1", 5, "start", "R1")
        logger.log_event("C1", "Activity1", 10, "complete", "R1")
        logger.log_event("C2", "Activity1", 2, "start", "R2")
        
        df = logger.get_dataframe()
        
        assert isinstance(df, pd.DataFrame)
        assert len(df) == 3
        assert "case_id" in df.columns
        assert "activity" in df.columns
        assert "timestamp" in df.columns
        assert "lifecycle" in df.columns
        assert "resource" in df.columns
    
    def test_dataframe_sorted(self):
        """Test that DataFrame is sorted by case_id and timestamp."""
        logger = EventLogger()
        
        logger.log_event("C2", "Activity1", 15, "complete")
        logger.log_event("C1", "Activity1", 5, "start")
        logger.log_event("C1", "Activity1", 10, "complete")
        
        df = logger.get_dataframe()
        
        # Check sorting
        assert df.iloc[0]["case_id"] == "C1"
        assert df.iloc[0]["timestamp"] == 5
        assert df.iloc[1]["case_id"] == "C1"
        assert df.iloc[1]["timestamp"] == 10
        assert df.iloc[2]["case_id"] == "C2"
    
    def test_export_to_csv(self, tmp_path):
        """Test exporting events to CSV."""
        logger = EventLogger()
        
        logger.log_event("C1", "Activity1", 5, "start")
        logger.log_event("C1", "Activity1", 10, "complete")
        
        # Use temporary directory for test file
        csv_file = tmp_path / "test_events.csv"
        df = logger.export_to_csv(str(csv_file))
        
        assert csv_file.exists()
        assert len(df) == 2
        
        # Verify CSV can be read back
        df_read = pd.read_csv(csv_file)
        assert len(df_read) == 2
        assert "case_id" in df_read.columns