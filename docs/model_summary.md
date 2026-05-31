# Model Summary

## Scope

The model evaluates a EUR 300B EU Global Gateway investment shock in a
GLORIA-based MRIO system with 164 countries and 120 sectors. It links the
investment shock to value added, CO2, supply-chain spillovers, and
carbon-footprint inequality across 201 within-country income groups.

## Main Workflow

1. `EUGG_model.m` loads GLORIA matrices and local investment inputs,
   constructs the MRIO shock, computes country and global outcomes, and writes
   local workbook sheets 1-9 and 15-17.
2. `EUGG_analysis.m` reads the local workbook and workspace, then appends the
   extended Theil decomposition and Lorenz data sheets 10-14.
3. `EUGG_figures.py` and `chapter4_figures.py` provide local plotting code.
   Generated figures are excluded from Git.

## Inequality Metrics

The model reports both global Gini and Theil T. Theil T is decomposed into
between-country and within-country components so users can evaluate whether
aggregate distributional changes come from cross-country divergence,
within-country distributional shifts, or both.

## Data Policy

Raw and intermediate GLORIA matrices, generated workbooks, generated figures,
and numerical model outputs are excluded from the repository. The published code
assumes that users obtain licensed source data separately and place processed
local files under `data/input/`.
