# Project Structure

```text
desk/
│
├── __init__.py
|
├── distfit/
│   ├── __init__.py
│   ├── distfit.py             # DistFit CLI tool
|   └── data1.txt              # Input data (data1.txt...data26.txt) 
│
├── core/
│   ├── __init__.py
│   ├── entity.py              # Entity, EventLogger
│   ├── base_block.py          # BaseBlock (abstract)
│   ├── simulation_model.py    # SimulationModel (slim core)
|   ├── model_variables.py     # ModelVariable (custom variables)
|   ├── simulation_observer.py # SimulationObserver (computing variables)
|   └── event_tracer.py        # EventTracer (for debug, with icons, or visualization in BupaR)
│
├── blocks/
│   ├── __init__.py
│   ├── create_block.py        # CreateBlock
│   ├── process_block.py       # ProcessBlock, MultiProcessBlock
│   ├── decide_block.py        # DecideBlock
│   └── dispose_block.py       # DisposeBlock
│
├── analytics/
│   ├── __init__.py
│   ├── metrics.py             # MetricsCollector
│   ├── wip_metrics.py         # WIP MetricsCollector
│   ├── reporting.py           # SimulationReporter
│   ├── financial.py           # FinancialAnalyzer
│   └── plotting.py            # SimulationPlotter
│
├── validation/
│   ├── __init__.py
│   ├── stability.py           # StabilityAnalyzer
│   ├── resource_validator.py  # ResourceValidator
│   └── warmup.py              # WarmUpAnalyzer
│
├── stats/
│   ├── __init__.py
│   ├── replication.py         # ReplicationFramework
│   └── factorial.py           # FactorialExperiment
│
├── config/
│   ├── __init__.py
│   └── simulation_config.py   # SimulationConfig
│
├── utils/
│   ├── __init__.py
│   └── helpers.py             # safe_delay_time, etc.
│
├── examples/
│   ├── __init__.py
│   ├── hospital_example.py
│   └── simple_queue_example.py
│
├── r_animation/
│   ├── .RData              # R Workspace
│   ├── hospital_bupar.R    # R animation flow
│   ├── ex1_bupar.R         # R animation flow
│   ├── ex2_bupar.R         # R animation flow
│   ├── ex3_bupar.R         # R animation flow
│   ├── ex3a_bupar.R        # R animation flow
│   └── ex3b_bupar.R        # R animation flow
│
└── tests/
    ├── __init__.py
    ├── conftest.py
    ├── test_core/
    ├── test_blocks/
    ├── test_analytics/
    ├── test_integration/
    ├── test_statistics/
    └── test_validation/
```