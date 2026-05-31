# EU Global Gateway MRIO Carbon Inequality Model

This repository contains the model code for analysing how EU Global Gateway
investment affects global carbon-footprint inequality in a GLORIA-based
multi-regional input-output framework.

The current public code corresponds to the V6 population-weight rerun used in
the thesis chapter on global EUGG results. Raw GLORIA matrices and local thesis
outputs are not included because of file size and data-licensing constraints.

## What The Model Does

- Builds a 164-country by 120-sector MRIO investment shock model.
- Allocates the EUR 300B EUGG investment package across countries and sectors.
- Estimates induced value added, CO2, EU supply-chain spillovers, and country
  carbon-footprint distribution changes.
- Computes weighted Gini and Theil T decomposition across
  country-income-group observations.
- Runs 15 mitigation combinations: 5 sectoral allocations by 3 technology
  transfer levels.
- Generates publication-ready figures from the model workbook.

## Current Verified Headline Results

Using World Bank 2023 country population weights:

| Metric | Value |
| --- | ---: |
| Total EUGG investment | EUR 300B |
| MRIO coverage | 164 countries x 120 sectors |
| Valid country-income-group observations | 28,295 |
| Total GDP induced | EUR 362.5B |
| Total CO2 induced | 293.9 Mt |
| EU supply-chain spillover GDP | EUR 62.5B |
| EU supply-chain spillover CO2 | 27.7 Mt |
| Global Gini change | +2.22 x 10^-4 |
| Total Theil T change | -1.65 x 10^-3 |
| Between-country Theil change | +3.45 x 10^-4 |
| Within-country Theil change | -2.00 x 10^-3 |
| Countries with lower domestic Gini | 86 / 164 |

The inequality interpretation is metric-sensitive: global Gini rises, while
total Theil T falls because within-country compression exceeds the increase in
the between-country component.

## Repository Layout

```text
.
├── EUGG_model_V6_0.m                         # main MRIO model and scenarios
├── EUGG_Analysis_V6_0.m                      # extended Theil analysis
├── EUGG_Figures_V6_0.py                      # 15 global figures
├── EUGG_Figures_Chapter4_Supplementary.py    # thesis Chapter 4 figures
├── build_country_population_weights.py       # World Bank population weights
├── run_pipeline.m                            # MATLAB model + analysis runner
├── data/
│   ├── input/                                # local-only model inputs
│   └── mapping/                              # local-only mapping workbook
├── docs/
│   └── model_summary.md
└── results/                                  # generated locally, not tracked
```

## Required Inputs

Place the required files in `data/input/`. The model expects:

- `FD2023.mat` with variable `FD`
- `UT2023.mat` with variable `UT`
- `V2023.mat` with variable `v`
- `va_f.mat` with variable `va_f`
- `CO2_2023.mat` with variable `CO2_2023`
- `C_matrix.mat` with variable `C`
- `pop_weights.mat` with `Pop_Weight_matrix` and `Pop_Weight_global`
- `country_population_weights_wb_2023.csv`
- `Data.xlsx`
- `World Bank Country Class_2025_10_07.xlsx`
- `Investment matrix_GLORIA.xlsx`

To rebuild the country population CSV, place
`mapping regions_WBhh_GLORIA_WBpop_EDGAR.xlsx` in `data/mapping/`, then run:

```bash
python build_country_population_weights.py
```

## Running The Pipeline

Install Python plotting dependencies:

```bash
python -m pip install -r requirements.txt
```

Run the MATLAB model and extended analysis:

```bash
matlab -batch "run('run_pipeline.m')"
```

Generate the figure set:

```bash
python EUGG_Figures_V6_0.py
python EUGG_Figures_Chapter4_Supplementary.py
```

Generated files are written to:

- `results/Data/EUGG_Results.xlsx`
- `results/Data/EUGG_Workspace.mat`
- `results/Figures/`

## Data Availability

The repository does not redistribute GLORIA source matrices, local workbook
inputs, or thesis draft files. Users should obtain GLORIA data from the official
source and place the processed matrices in `data/input/`.

## License

Code is released under the MIT License. Data inputs remain subject to their
original providers' licenses.
