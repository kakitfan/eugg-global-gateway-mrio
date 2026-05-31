# Model Summary

## Scope

The model evaluates a EUR 300B EU Global Gateway investment shock in a
GLORIA-based MRIO system with 164 countries and 120 sectors. It links the
investment shock to value added, CO2, supply-chain spillovers, and
carbon-footprint inequality across 201 within-country income groups.

## Main Workflow

1. `EUGG_model_V6_0.m` loads GLORIA matrices and local investment inputs,
   constructs the MRIO shock, computes country and global outcomes, and writes
   workbook sheets 1-9 and 15-17.
2. `EUGG_Analysis_V6_0.m` reads the workbook and workspace, then appends the
   extended Theil decomposition and Lorenz data sheets 10-14.
3. `EUGG_Figures_V6_0.py` generates the main 15-figure global output set.
4. `EUGG_Figures_Chapter4_Supplementary.py` generates the Chapter 4 thesis
   figure subset.

## Inequality Metrics

The model reports both global Gini and Theil T. The current population-weight
rerun gives a metric-sensitive result: the global carbon-footprint Gini rises,
but total Theil T falls because within-country compression exceeds
between-country divergence. The between-country Theil component still rises.

## Data Policy

Raw and intermediate GLORIA matrices are excluded from the repository. The
published code assumes that users obtain licensed source data separately and
place processed local files under `data/input/`.
