## DESK Distribution Fitting Tool (Desk-DistFit)

### 📊 Input Analysis with Desk-DistFit

Desk DistFit (`desk-distfit`) is a Python tool for fitting probability distributions to empirical data using statistical tests. Inspired by previous works [6,7], this tool helps identify the best-fitting probability distribution from a set of common distributions and provides Python code for generating random numbers from the fitted distribution to DESK models. 


`desk-distfit` is the official DESK input-analysis CLI for statistically fitting probability distributions to empirical data. 


## Features

- **Multiple Distribution Support**: Tests 9 common probability distributions (uniform, triangular, exponential, normal, lognormal, beta, gamma, Weibull)
- **Statistical Testing**: Uses Kolmogorov-Smirnov test for goodness-of-fit assessment
- **Command-Line Interface**: Easy-to-use CLI with comprehensive options
- **Multiple Output Formats**: Results can be saved as table, CSV, or JSON
- **Visualization**: Generates comparative plots of fitted distributions
- **Python Code Generation**: Automatically generates Python code for the best-fitting distribution
- **Robust Error Handling**: Comprehensive error handling and logging

**Output includes:**

* Goodness-of-fit statistics
* Best-fit distribution
* Parameter estimates
* Ready-to-use Python code for DESK models, such as the texts `random.expovariate(1/10)` or `random.uniform(5, 10)`.

## Usage

### Basic Usage

Fit probability distributions to empirical data:

```bash
# Basic usage
desk-distfit -d input_data/foo.txt

# Custom significance level
desk-distfit -d input_data/foo.txt -a 0.01

# Test specific distributions
desk-distfit -d input_data/foo.txt --distributions norm expon gamma

# Save results
desk-distfit -d input_data/foo.txt -o results.txt --format json

# Skip plotting
desk-distfit -d input_data/foo.txt --no-plot

# Help
desk-distfit -h
```


### Command-Line Options

| Option | Description | Default |
|--------|-------------|---------|
| `-d, --data` | Path to data file (required) | - |
| `-a, --alpha` | Significance level for statistical tests | 0.05 |
| `-b, --bins` | Number of histogram bins | 50 |
| `--distributions` | Specific distributions to test | All |
| `--no-plot` | Skip generating plots | False |
| `--show-all` | Show all distributions in plot | False |
| `-o, --output` | Output file path | None |
| `--format` | Output format (table/csv/json) | table |
| `-v, --verbose` | Enable verbose logging | False |
| `-h, --help` | Show help message | - |

### Examples

```bash
# Basic analysis
desk-distfit -d input_data/foo.txt

# Custom significance level
desk-distfit -d input_data/foo.txt -a 0.01

# Test specific distributions only
desk-distfit -d input_data/foo.txt --distributions norm expon gamma

# Save results to file
desk-distfit -d input_data/foo.txt -o results.txt

# Generate CSV output
desk-distfit -d input_data/foo.txt -o results.csv --format csv

# Skip plotting (useful for batch processing)
desk-distfit -d input_data/foo.txt --no-plot

# Show all fitted distributions in plot
desk-distfit -d input_data/foo.txt --show-all

# Verbose output for debugging
desk-distfit -d input_data/foo.txt -v

# Complete example with multiple options
desk-distfit -d input_data/foo.txt -a 0.01 -b 100 --show-all -o results.json --format json -v
```

## Input Data Format

The input file should contain one numeric value per line:

```
1.234
2.567
0.891
3.456
...
```

**Supported formats:**
- Plain text files (.txt)
- One number per line
- UTF-8 encoding
- Blank lines are ignored

## Supported Distributions

| Distribution | Python Random Function | Parameters |
|-------------|------------------------|------------|
| Uniform | `random.uniform(a, b)` | a, b |
| Triangular | `random.triangular(low, high, mode)` | low, high, mode |
| Exponential | `random.expovariate(lambd)` | lambda |
| Normal | `random.gauss(mu, sigma)` | mu, sigma |
| Log-Normal | `random.lognormvariate(mu, sigma)` | mu, sigma |
| Beta | `random.betavariate(alpha, beta)` | alpha, beta |
| Gamma | `random.gammavariate(alpha, beta)` | alpha, beta |
| Weibull (Min) | `random.weibullvariate(alpha, beta)` | alpha, beta |
| Weibull (Max) | `random.weibullvariate(alpha, beta)` | alpha, beta |

## Output

### Console Output

The tool provides:
1. **Data statistics** (sample size, mean, std dev, min, max)
2. **Distribution fitting results** with p-values and significance indicators
3. **Parameter details** for all fitted distributions
4. **Summary report** with best-fitting distribution
5. **Python code** for generating random numbers for DESK model.

### Example Output

```
Data Statistics:
Sample size: 200
Mean: 2.0156
Std Dev: 2.0298
Min: 0.0089
Max: 11.2445

Item Distribution   Statistic   P-value     Significant
------------------------------------------------------------
1    expon          0.0456      0.8234      (*)
2    gamma          0.0523      0.7891      (*)
3    norm           0.0789      0.4567      
...

Distribution Fitting Summary Report
==================================================

Best Fitting Distribution: expon
- Parameters: loc=0.000, scale=2.016
- P-value: 0.8234
- Significant at α=0.05: Yes

Python Random Code:
random.expovariate(0.496)
```

### File Output Formats

#### Table Format (default)
Human-readable text format with detailed results and parameters.

#### CSV Format
```csv
Distribution,P_value,Statistic,Significant,Python_Code
expon,0.823400,0.045600,Yes,random.expovariate(0.496)
gamma,0.789100,0.052300,Yes,random.gammavariate(1.024,0.496)
...
```

#### JSON Format
```json
{
  "summary": {
    "sample_size": 200,
    "best_distribution": "expon",
    "alpha": 0.05
  },
  "results": [
    {
      "distribution": "expon",
      "p_value": 0.8234,
      "statistic": 0.0456,
      "parameters": {"loc": 0.0, "scale": 2.016},
      "significant": true,
      "python_code": "random.expovariate(0.496)"
    }
  ]
}
```

## Interpretation

### P-Values
- **p ≥ α**: Distribution is a good fit (significant)
- **p < α**: Distribution is not a good fit (reject)
- Higher p-values indicate better fits

### Significance Indicators
- **(*) asterisk**: Indicates significant fit at the chosen α level
- Results are sorted by p-value (best fit first)



## Statistical Method

The tool uses the **Kolmogorov-Smirnov test** [8] to assess goodness-of-fit:

1. **Null Hypothesis (H₀)**: The data follows the tested distribution
2. **Alternative Hypothesis (H₁)**: The data does not follow the tested distribution
3. **Test Statistic**: Maximum difference between empirical and theoretical CDFs
4. **Decision Rule**: Reject H₀ if p-value < α

## Limitations

- **Sample Size**: Requires sufficient data points (recommended: n ≥ 30)
- **Distribution Assumptions**: Only tests common continuous distributions
- **Parameter Estimation**: Uses Maximum Likelihood Estimation (MLE)
- **Independence**: Assumes data points are independent
- **Stationarity**: Assumes data comes from a stationary process


### Help (DESK and DESK-DistFit)

```bash
# Show detailed help
desk-distfit -h

# Enable verbose output for debugging
desk-distfit -d input_data/foo.txt -v
```