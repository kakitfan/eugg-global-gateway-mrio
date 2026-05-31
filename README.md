# EU Global Gateway MRIO Carbon Inequality Model

This repository contains the model code for analysing how EU Global Gateway
investment affects global carbon-footprint inequality in a GLORIA-based
multi-regional input-output framework.

This repository provides the model method and reproducible code structure only.
It does not publish model-generated workbooks, figures, numerical results, raw
GLORIA matrices, or local thesis outputs.

## What The Model Does

- Builds a 164-country by 120-sector MRIO investment shock model.
- Allocates the EUR 300B EUGG investment package across countries and sectors.
- Estimates induced value added, CO2, EU supply-chain spillovers, and country
  carbon-footprint distribution changes.
- Computes weighted Gini and Theil T decomposition across
  country-income-group observations.
- Runs 15 mitigation combinations: 5 sectoral allocations by 3 technology
  transfer levels.
- Includes plotting code for local reproduction. Generated figures are ignored
  by Git and are not published in this repository.

## Repository Layout

```text
.
├── EUGG_model.m                              # main MRIO model and scenarios
├── EUGG_analysis.m                           # extended Theil analysis
├── EUGG_figures.py                           # local figure generation script
├── chapter4_figures.py                       # local supplementary figure script
├── build_country_population_weights.py       # World Bank population weights
├── run_pipeline.m                            # MATLAB model + analysis runner
├── data/
│   ├── input/                                # local-only model inputs
│   └── mapping/                              # local-only mapping workbook
├── docs/
│   └── model_summary.md
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
python EUGG_figures.py
python chapter4_figures.py
```

Generated local files are written to the ignored `results/` directory:

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
