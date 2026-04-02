---
title: 'DESK: A replication and experimental design-oriented framework for discrete-event simulation'
tags:
  - discrete-event simulation
  - replication analysis
  - factorial design
  - python
  - operations research
authors:
  - name: "João Flávio de Freitas Almeida"
    orcid: 0000-0002-3884-217X
    affiliation: 1
affiliations:
  - name: Graduate Program in Production Engineering (PPGEP), Federal University of Minas Gerais (UFMG), Brazil
    index: 1
date: 11 January 2025
bibliography: paper.bib

---

# Summary

Discrete-event simulation (DES) is a widely adopted methodology for analyzing complex stochastic systems in operations research, logistics, healthcare, and service systems [@banks2010discrete; @law2015simulation]. Although there are mature simulation engines for model execution, researchers and students often encounter recurring challenges related to experiment design, replication management, and systematic result aggregation. These steps are often implemented ad hoc, which reduces reproducibility and increases development effort [@stodden2016reproducibility].

DESK (Discrete Event Simulation Kit) is an open-source framework designed to support the experimental workflow of discrete-event simulation studies. Rather than focusing solely on model execution, DESK provides explicit abstractions for replication analysis, factorial experiments, scenario-based experiments, and the automated aggregation of performance metrics. DESK promotes reproducible and transparent simulation studies and is suitable for applied decision support, research and teaching applications.

# Statement of need

Simulation-based studies typically require multiple replications, parameter variations, and statistical analysis of outputs to ensure valid inferences [@law2015simulation; @kleijnen2015design]. Despite their central role in scientific studies, these experimental components are rarely treated as primary entities in simulation software. Consequently, researchers often reimplement replication loops, parameter variations, and result aggregation logic across projects, which increases the risk of errors and limits reproducibility [@banks2010discrete].

DESK addresses this issue by structuring simulation experiments as configurable, reusable software components. The framework separates model logic from experimental design, enabling systematic replication analysis and factorial experiments without modifying the core simulation code. This approach supports reproducible research practices [@stodden2016reproducibility] and lowers the barrier to conducting rigorous simulation experiments, particularly in academic and educational contexts.

# State of the Field

Several established tools support discrete-event simulation, including open-source libraries such as SimPy [@matloff2008introduction], commercial simulation platforms, and domain-specific simulators. These tools provide robust mechanisms for event scheduling and process interaction but typically leave experiment orchestration, replication management, and experimental design to the user.

DESK is designed to complement existing simulation engines by focusing on the organization and execution of simulation experiments rather than on simulation performance or low-level execution mechanisms. Its design is aligned with established principles for the design and analysis of simulation experiments [@kleijnen2015design], while remaining interoperable with existing DES modeling approaches.

# Software design

DESK is implemented in Python and follows a modular architecture that separates simulation models, experimental configuration, and analysis, in line with best practices in simulation modeling [@law2015simulation].

## Core architecture
The framework provides:

* A simulation model abstraction for managing entities, resources, and event scheduling
* Modular building blocks for common simulation activities (e.g., creation, processing, and disposal)
* Centralized event logging to support post-simulation analysis and validation

This structure supports model transparency and facilitates verification and validation activities recommended in the simulation literature [@banks2010discrete].

## Replication framework

DESK includes a replication framework that automates the execution of multiple simulation runs with controlled random seeds, warm-up periods, and simulation horizons. Results from individual replications are aggregated into structured data objects suitable for statistical analysis, following established guidelines for output analysis in simulation studies [@law2015simulation; @kleijnen2015design].

## Factorial and scenario analysis
The framework supports factorial experiments by allowing users to define factors, levels, and parameter paths. DESK automatically generates experimental configurations, executes replications for each scenario, for analyzing main and interaction effects. This functionality directly supports classical and modern approaches to the design and analysis of simulation experiments [@montgomery2017design; @kleijnen2015design].

## Validation and diagnostics
To ensure model reliability, DESK incorporates automated validation and diagnostic tools. Stability analysis checks resource utilization to verify system capacity and prevent unrealistic queue buildup. 
Warm-up period detection identifies the transient phase through time-series analysis of performance metrics, suggesting truncation points for steady-state analysis. Resource consistency validation confirms proper allocation and release, detecting potential deadlocks or leaks.

## Input analysis (`desk-distfit`)
DESK includes a dedicated input analysis tool, `desk-distfit`, for fitting probability distributions to empirical data using statistical methods and automatic generation of Python code snippets, facilitating direct integration into DESK simulation models. This command-line tool supports nine common continuous distributions, including uniform, triangular, exponential, normal, lognormal, beta, gamma, and Weibull (both min and max variants). It employs the Kolmogorov-Smirnov test for goodness-of-fit assessment at user-specified significance levels.

The tool processes input data from text files, computes descriptive statistics, and ranks distributions by p-value. Output options include tabular summaries, CSV, or JSON formats, with optional histogram visualizations comparing fitted distributions to empirical data.

# Visualization and event tracing
DESK provides transparency through visualization and tracing capabilities. Real-time graphical interfaces display entity flows, resource states, and queue dynamics during simulation execution, synchronized with event logs for step-by-step inspection.

Event tracing captures detailed logs with filtering options, enabling replay and debugging. Post-simulation visualizations include resource utilization plots, work-in-process evolution, system time distributions, and activity metrics.

Integration with BupaR (via processanimateR) exports event logs for advanced process mining and animated replays in R, enhancing model understanding and communication [@law2015simulation]. These features promote model transparency by making abstract simulation concepts visually accessible.



# AI usage disclosure

During the development of DESK, AI tools including Claude Sonnet 4.5, Grok 4.0, and ChatGPT-4.1 were utilized for refactoring code and generating tests, while DeepL translator 1.68 was employed for improvements to the paper's text. The author asserts that they reviewed, edited, and validated all AI-assisted outputs and made the core design decisions.

# Acknowledgements

We acknowledge contributions from UFMG, CAPES, CNPq and FAPEMIG during the genesis of this project.

# References