# tests/conftest.py
"""
Pytest configuration file with shared fixtures.
"""
import sys, os
sys.path.append(os.path.dirname(os.path.dirname(__file__)))

import pytest
import simpy
from desk.core.simulation_model import SimulationModel
from desk.core.entity import EventLogger


@pytest.fixture
def env_with_model(event_logger):
    """
    SimPy environment with attached DESK SimulationModel.
    Matches the real SimulationModel API.
    """
    env = simpy.Environment()
    model = SimulationModel()
    model.env = env
    model.event_logger = event_logger
    env.model = model
    return env



@pytest.fixture
def simple_env():
    """Create a simple SimPy environment."""
    return simpy.Environment()


@pytest.fixture
def simple_model():
    """Create a simple simulation model."""
    return SimulationModel()


@pytest.fixture
def event_logger():
    """Create an event logger."""
    return EventLogger()


@pytest.fixture
def seed_value():
    """Standard seed for reproducible tests."""
    return 12345