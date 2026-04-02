### Factorial Analysis

- **Factorial Experiments**: Full factorial design with interaction analysis

### 📊 Running a factorial experiment 

Runs a **factorial experiment**, varying model parameters and analyzing main and interaction effects.

```bash
desk-sim -m examples/hospital.py --mode factorial
```

![Use](figs/factorial.png)
---

(Report for the example `hospital.py`)

```
🔬 FACTORIAL EXPERIMENT
============================================================
Factors: 3
  - arrival_rate: 3 levels
  - num_doctors: 3 levels
  - num_nurses: 3 levels
Combinations: 27
Replications per combination: 5
Total runs: 135
============================================================

📊 Settings 1/27: {'arrival_rate': 3, 'num_doctors': 3, 'num_nurses': 2}
  Replication 1/5 (seed: 12345)
  Replication 2/5 (seed: 12346)
  Replication 3/5 (seed: 12347)
  Replication 4/5 (seed: 12348)
  Replication 5/5 (seed: 12349)

📊 Settings 2/27: {'arrival_rate': 3, 'num_doctors': 3, 'num_nurses': 3}
  Replication 1/5 (seed: 13345)
  Replication 2/5 (seed: 13346)
  Replication 3/5 (seed: 13347)
  Replication 4/5 (seed: 13348)
  Replication 5/5 (seed: 13349)
  Progress: 10/135 | Remaining time: 0.2 min

📊 Settings 3/27: {'arrival_rate': 3, 'num_doctors': 3, 'num_nurses': 4}
  Replication 1/5 (seed: 14345)
  Replication 2/5 (seed: 14346)
  Replication 3/5 (seed: 14347)
  Replication 4/5 (seed: 14348)
  Replication 5/5 (seed: 14349)

📊 Settings 4/27: {'arrival_rate': 3, 'num_doctors': 4, 'num_nurses': 2}
  Replication 1/5 (seed: 15345)
  Replication 2/5 (seed: 15346)
  Replication 3/5 (seed: 15347)
  Replication 4/5 (seed: 15348)
  Replication 5/5 (seed: 15349)
  Progress: 20/135 | Remaining time: 0.2 min

📊 Settings 5/27: {'arrival_rate': 3, 'num_doctors': 4, 'num_nurses': 3}
  Replication 1/5 (seed: 16345)
  Replication 2/5 (seed: 16346)
  Replication 3/5 (seed: 16347)
  Replication 4/5 (seed: 16348)
  Replication 5/5 (seed: 16349)

📊 Settings 6/27: {'arrival_rate': 3, 'num_doctors': 4, 'num_nurses': 4}
  Replication 1/5 (seed: 17345)
  Replication 2/5 (seed: 17346)
  Replication 3/5 (seed: 17347)
  Replication 4/5 (seed: 17348)
  Replication 5/5 (seed: 17349)
  Progress: 30/135 | Remaining time: 0.2 min

📊 Settings 7/27: {'arrival_rate': 3, 'num_doctors': 5, 'num_nurses': 2}
  Replication 1/5 (seed: 18345)
  Replication 2/5 (seed: 18346)
  Replication 3/5 (seed: 18347)
  Replication 4/5 (seed: 18348)
  Replication 5/5 (seed: 18349)

📊 Settings 8/27: {'arrival_rate': 3, 'num_doctors': 5, 'num_nurses': 3}
  Replication 1/5 (seed: 19345)
  Replication 2/5 (seed: 19346)
  Replication 3/5 (seed: 19347)
  Replication 4/5 (seed: 19348)
  Replication 5/5 (seed: 19349)
  Progress: 40/135 | Remaining time: 0.2 min

📊 Settings 9/27: {'arrival_rate': 3, 'num_doctors': 5, 'num_nurses': 4}
  Replication 1/5 (seed: 20345)
  Replication 2/5 (seed: 20346)
  Replication 3/5 (seed: 20347)
  Replication 4/5 (seed: 20348)
  Replication 5/5 (seed: 20349)

📊 Settings 10/27: {'arrival_rate': 4, 'num_doctors': 3, 'num_nurses': 2}
  Replication 1/5 (seed: 21345)
  Replication 2/5 (seed: 21346)
  Replication 3/5 (seed: 21347)
  Replication 4/5 (seed: 21348)
  Replication 5/5 (seed: 21349)
  Progress: 50/135 | Remaining time: 0.1 min

📊 Settings 11/27: {'arrival_rate': 4, 'num_doctors': 3, 'num_nurses': 3}
  Replication 1/5 (seed: 22345)
  Replication 2/5 (seed: 22346)
  Replication 3/5 (seed: 22347)
  Replication 4/5 (seed: 22348)
  Replication 5/5 (seed: 22349)

📊 Settings 12/27: {'arrival_rate': 4, 'num_doctors': 3, 'num_nurses': 4}
  Replication 1/5 (seed: 23345)
  Replication 2/5 (seed: 23346)
  Replication 3/5 (seed: 23347)
  Replication 4/5 (seed: 23348)
  Replication 5/5 (seed: 23349)
  Progress: 60/135 | Remaining time: 0.1 min

📊 Settings 13/27: {'arrival_rate': 4, 'num_doctors': 4, 'num_nurses': 2}
  Replication 1/5 (seed: 24345)
  Replication 2/5 (seed: 24346)
  Replication 3/5 (seed: 24347)
  Replication 4/5 (seed: 24348)
  Replication 5/5 (seed: 24349)

📊 Settings 14/27: {'arrival_rate': 4, 'num_doctors': 4, 'num_nurses': 3}
  Replication 1/5 (seed: 25345)
  Replication 2/5 (seed: 25346)
  Replication 3/5 (seed: 25347)
  Replication 4/5 (seed: 25348)
  Replication 5/5 (seed: 25349)
  Progress: 70/135 | Remaining time: 0.1 min

📊 Settings 15/27: {'arrival_rate': 4, 'num_doctors': 4, 'num_nurses': 4}
  Replication 1/5 (seed: 26345)
  Replication 2/5 (seed: 26346)
  Replication 3/5 (seed: 26347)
  Replication 4/5 (seed: 26348)
  Replication 5/5 (seed: 26349)

📊 Settings 16/27: {'arrival_rate': 4, 'num_doctors': 5, 'num_nurses': 2}
  Replication 1/5 (seed: 27345)
  Replication 2/5 (seed: 27346)
  Replication 3/5 (seed: 27347)
  Replication 4/5 (seed: 27348)
  Replication 5/5 (seed: 27349)
  Progress: 80/135 | Remaining time: 0.1 min

📊 Settings 17/27: {'arrival_rate': 4, 'num_doctors': 5, 'num_nurses': 3}
  Replication 1/5 (seed: 28345)
  Replication 2/5 (seed: 28346)
  Replication 3/5 (seed: 28347)
  Replication 4/5 (seed: 28348)
  Replication 5/5 (seed: 28349)

📊 Settings 18/27: {'arrival_rate': 4, 'num_doctors': 5, 'num_nurses': 4}
  Replication 1/5 (seed: 29345)
  Replication 2/5 (seed: 29346)
  Replication 3/5 (seed: 29347)
  Replication 4/5 (seed: 29348)
  Replication 5/5 (seed: 29349)
  Progress: 90/135 | Remaining time: 0.1 min

📊 Settings 19/27: {'arrival_rate': 5, 'num_doctors': 3, 'num_nurses': 2}
  Replication 1/5 (seed: 30345)
  Replication 2/5 (seed: 30346)
  Replication 3/5 (seed: 30347)
  Replication 4/5 (seed: 30348)
  Replication 5/5 (seed: 30349)

📊 Settings 20/27: {'arrival_rate': 5, 'num_doctors': 3, 'num_nurses': 3}
  Replication 1/5 (seed: 31345)
  Replication 2/5 (seed: 31346)
  Replication 3/5 (seed: 31347)
  Replication 4/5 (seed: 31348)
  Replication 5/5 (seed: 31349)
  Progress: 100/135 | Remaining time: 0.1 min

📊 Settings 21/27: {'arrival_rate': 5, 'num_doctors': 3, 'num_nurses': 4}
  Replication 1/5 (seed: 32345)
  Replication 2/5 (seed: 32346)
  Replication 3/5 (seed: 32347)
  Replication 4/5 (seed: 32348)
  Replication 5/5 (seed: 32349)

📊 Settings 22/27: {'arrival_rate': 5, 'num_doctors': 4, 'num_nurses': 2}
  Replication 1/5 (seed: 33345)
  Replication 2/5 (seed: 33346)
  Replication 3/5 (seed: 33347)
  Replication 4/5 (seed: 33348)
  Replication 5/5 (seed: 33349)
  Progress: 110/135 | Remaining time: 0.0 min

📊 Settings 23/27: {'arrival_rate': 5, 'num_doctors': 4, 'num_nurses': 3}
  Replication 1/5 (seed: 34345)
  Replication 2/5 (seed: 34346)
  Replication 3/5 (seed: 34347)
  Replication 4/5 (seed: 34348)
  Replication 5/5 (seed: 34349)

📊 Settings 24/27: {'arrival_rate': 5, 'num_doctors': 4, 'num_nurses': 4}
  Replication 1/5 (seed: 35345)
  Replication 2/5 (seed: 35346)
  Replication 3/5 (seed: 35347)
  Replication 4/5 (seed: 35348)
  Replication 5/5 (seed: 35349)
  Progress: 120/135 | Remaining time: 0.0 min

📊 Settings 25/27: {'arrival_rate': 5, 'num_doctors': 5, 'num_nurses': 2}
  Replication 1/5 (seed: 36345)
  Replication 2/5 (seed: 36346)
  Replication 3/5 (seed: 36347)
  Replication 4/5 (seed: 36348)
  Replication 5/5 (seed: 36349)

📊 Settings 26/27: {'arrival_rate': 5, 'num_doctors': 5, 'num_nurses': 3}
  Replication 1/5 (seed: 37345)
  Replication 2/5 (seed: 37346)
  Replication 3/5 (seed: 37347)
  Replication 4/5 (seed: 37348)
  Replication 5/5 (seed: 37349)
  Progress: 130/135 | Remaining time: 0.0 min

📊 Settings 27/27: {'arrival_rate': 5, 'num_doctors': 5, 'num_nurses': 4}
  Replication 1/5 (seed: 38345)
  Replication 2/5 (seed: 38346)
  Replication 3/5 (seed: 38347)
  Replication 4/5 (seed: 38348)
  Replication 5/5 (seed: 38349)

✅ EXPERIMENT COMPLETED in 0.2 minutes
⏱️  Average time per run: 0.1 seconds
📊 135 collected results

======================================================================
📊 SUMMARY OF FACTORIAL ANALYSIS
======================================================================

🔬 TESTED FACTORS:
  - arrival_rate: [3, 4, 5]
    Taxa de chegada de pacientes (min)
  - num_doctors: [3, 4, 5]
    Número de médicos
  - num_nurses: [2, 3, 4]
    Número de enfermeiros

  Pharmacy_queue_time:
    Best: {'arrival_rate': np.float64(4.0), 'num_doctors': np.float64(3.0), 'num_nurses': np.float64(4.0)} -> 0.48
    Worst: {'arrival_rate': np.float64(4.0), 'num_doctors': np.float64(3.0), 'num_nurses': np.float64(4.0)} -> 5.96

  nursesT_utilization:
    Best: {'arrival_rate': np.float64(5.0), 'num_doctors': np.float64(4.0), 'num_nurses': np.float64(4.0)} -> 69.2%
    Worst: {'arrival_rate': np.float64(5.0), 'num_doctors': np.float64(4.0), 'num_nurses': np.float64(4.0)} -> 69.2%

📈 DESCRIPTIVE STATISTICS (Key Metrics):
----------------------------------------------------------------------

🕐 ACTIVITY TIMES:
                               mean       std       min        max
Pharmacy_queue_time        1.371925  0.626053  0.484948   5.955253
Pharmacy_service_time      4.992151  0.238217  4.256399   5.747871
Triage_queue_time          2.094812  0.391216  1.147587   3.687220
Triage_service_time        2.500689  0.014487  2.461689   2.536664
Consultation_queue_time    1.815384  0.719122  0.566440   4.889712
Consultation_service_time  9.999682  0.162553  9.573695  10.424390

🏭 USE OF RESOURCES:
                           mean       std        min        max
nursesT_utilization   62.399619  2.850914  55.509991  69.169869
doctors_utilization   53.748034  3.839807  45.712466  64.048544
nurses_utilization    67.366832  3.842249  58.935729  77.249431
pharmacy_utilization  51.563311  3.685842  39.735477  63.537011
(values in %)

💡 GENERAL ANALYSIS:
   Total number of configurations tested: 27
   Replications per configuration: 5
   Total executions: 135

Correlation matrix generated with 13 variables
📁 FULL results exported to results/factorial_results.csv
   Exported columns: 28
   Total entries: 135


Factorial analysis examples completed!
Check the generated CSV files and plots for detailed results.
```