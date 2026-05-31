#!/usr/bin/env python3
"""Build country population weights for the GLORIA EUGG model.

The existing pop_weights.mat file contains within-country income-group
weights only. This script adds country-level population totals from the
World Bank SP.POP.TOTL indicator and maps them to the 164 GLORIA country
rows used by the EUGG model. The mapping workbook is expected under
data/mapping/, and generated CSV files are written to data/input/.
"""

from __future__ import annotations

import json
import sys
import urllib.request
from pathlib import Path

import pandas as pd


YEAR = "2023"
INDICATOR = "SP.POP.TOTL"
WB_API = "https://api.worldbank.org/v2"

BASE_DIR = Path(__file__).resolve().parent
INPUT_DIR = BASE_DIR / "data" / "input"
MAPPING_DIR = BASE_DIR / "data" / "mapping"
MAPPING_FILE = (
    MAPPING_DIR
    / "mapping regions_WBhh_GLORIA_WBpop_EDGAR.xlsx"
)
OUT_WEIGHTS = INPUT_DIR / f"country_population_weights_wb_{YEAR}.csv"
OUT_RESIDUAL = INPUT_DIR / f"country_population_residual_members_wb_{YEAR}.csv"


REST_CODES = {"XAM", "XEU", "XAF", "XAS"}
DIRECT_OVERRIDES = {
    "PSE": "PSE",
    "SRB": "SRB",
}
ZERO_POPULATION_ROWS = {
    "DYE": "Historical South Yemen row; YEM carries current Yemen population.",
}
AFRICAN_MENA_CODES = {"DZA", "DJI", "EGY", "LBY", "MAR", "TUN"}


def fetch_json(url: str):
    with urllib.request.urlopen(url, timeout=60) as response:
        return json.loads(response.read().decode("utf-8"))


def fetch_country_metadata() -> pd.DataFrame:
    url = f"{WB_API}/country?format=json&per_page=400"
    payload = fetch_json(url)
    if not isinstance(payload, list) or len(payload) < 2:
        raise RuntimeError("Unexpected World Bank country metadata response.")

    rows = []
    for row in payload[1]:
        region = (row.get("region") or {}).get("value")
        income = (row.get("incomeLevel") or {}).get("value")
        rows.append(
            {
                "wb_code": row.get("id"),
                "wb_iso2": row.get("iso2Code"),
                "wb_name": row.get("name"),
                "wb_region": region.strip() if isinstance(region, str) else region,
                "wb_region_id": (row.get("region") or {}).get("id"),
                "wb_income": income.strip() if isinstance(income, str) else income,
                "wb_income_id": (row.get("incomeLevel") or {}).get("id"),
            }
        )
    return pd.DataFrame(rows)


def fetch_population() -> pd.DataFrame:
    url = (
        f"{WB_API}/country/all/indicator/{INDICATOR}"
        f"?format=json&date={YEAR}&per_page=20000"
    )
    payload = fetch_json(url)
    if not isinstance(payload, list) or len(payload) < 2:
        raise RuntimeError("Unexpected World Bank population response.")

    rows = []
    for row in payload[1]:
        rows.append(
            {
                "wb_code": row.get("countryiso3code"),
                "wb_name_population": (row.get("country") or {}).get("value"),
                "year": row.get("date"),
                "population": row.get("value"),
            }
        )
    df = pd.DataFrame(rows)
    df = df[df["population"].notna()].copy()
    df["population"] = df["population"].astype(float)
    return df


def classify_rest_region(row: pd.Series) -> str | None:
    code = row["wb_code"]
    region = row["wb_region"]
    if region == "Sub-Saharan Africa" or code in AFRICAN_MENA_CODES:
        return "XAF"
    if region in {"Latin America & Caribbean", "North America"}:
        return "XAM"
    if region == "Europe & Central Asia":
        return "XEU"
    if region in {"East Asia & Pacific", "South Asia", "Middle East & North Africa"}:
        return "XAS"
    return None


def main() -> int:
    if not MAPPING_FILE.exists():
        raise FileNotFoundError(MAPPING_FILE)
    INPUT_DIR.mkdir(parents=True, exist_ok=True)

    mapping = pd.read_excel(MAPPING_FILE, sheet_name="mapping")
    metadata = fetch_country_metadata()
    population = fetch_population()

    country_meta = metadata[
        (metadata["wb_region"] != "Aggregates")
        & (metadata["wb_income"] != "Aggregates")
    ].copy()
    pop_by_code = dict(zip(population["wb_code"], population["population"]))
    pop_name_by_code = dict(zip(population["wb_code"], population["wb_name_population"]))

    used_direct_codes: set[str] = set()
    output_rows = []

    for idx, row in mapping.iterrows():
        gloria_code = str(row["GLORIA_country_code"])
        wb_code = row.get("WB_pop_country_code")
        if pd.isna(wb_code):
            wb_code = DIRECT_OVERRIDES.get(gloria_code)
        else:
            wb_code = str(wb_code)

        population_value = None
        source = None
        note = ""

        if gloria_code in ZERO_POPULATION_ROWS:
            population_value = 0.0
            source = "zero_by_model_mapping"
            note = ZERO_POPULATION_ROWS[gloria_code]
            wb_code = ""
        elif gloria_code in REST_CODES:
            population_value = None
            source = "world_bank_residual"
            note = "Assigned after direct country mappings are removed."
            wb_code = ""
        elif wb_code:
            population_value = pop_by_code.get(wb_code)
            if population_value is None:
                raise RuntimeError(
                    f"No World Bank population value for GLORIA {gloria_code} / WB {wb_code}."
                )
            source = "world_bank_direct"
            if pd.isna(row.get("WB_pop_country_code")):
                note = "Manual direct override because mapping workbook has no WB_pop code."
            used_direct_codes.add(wb_code)
        else:
            raise RuntimeError(f"No population mapping rule for GLORIA row {gloria_code}.")

        output_rows.append(
            {
                "GLORIA_ID": idx + 1,
                "ISO3": gloria_code,
                "Country": row["GLORIA_country_name"],
                "GLORIA_region": row["GLORIA_region"],
                "WB_pop_country_code": wb_code,
                "WB_pop_country_name": pop_name_by_code.get(wb_code, "") if wb_code else "",
                "Population_2023": population_value,
                "Population_Source": source,
                "Population_Note": note,
            }
        )

    residual_candidates = country_meta[
        country_meta["wb_code"].isin(pop_by_code)
        & ~country_meta["wb_code"].isin(used_direct_codes)
    ].copy()
    residual_candidates["GLORIA_rest_code"] = residual_candidates.apply(
        classify_rest_region, axis=1
    )

    unclassified = residual_candidates[residual_candidates["GLORIA_rest_code"].isna()]
    if not unclassified.empty:
        codes = ", ".join(unclassified["wb_code"].astype(str).tolist())
        raise RuntimeError(f"Unclassified residual World Bank countries: {codes}")

    residual_candidates["Population_2023"] = residual_candidates["wb_code"].map(
        pop_by_code
    )
    residual_summary = (
        residual_candidates.groupby("GLORIA_rest_code", as_index=True)["Population_2023"]
        .sum()
        .to_dict()
    )

    for out_row in output_rows:
        if out_row["ISO3"] in REST_CODES:
            rest_code = out_row["ISO3"]
            out_row["Population_2023"] = float(residual_summary.get(rest_code, 0.0))
            members = residual_candidates[
                residual_candidates["GLORIA_rest_code"] == rest_code
            ]
            out_row["Population_Note"] = (
                f"Residual sum over {len(members)} World Bank countries or territories "
                "not mapped to named GLORIA rows."
            )

    out = pd.DataFrame(output_rows)
    if len(out) != 164:
        raise RuntimeError(f"Expected 164 GLORIA rows, got {len(out)}.")
    if out["Population_2023"].isna().any():
        missing = out[out["Population_2023"].isna()]["ISO3"].tolist()
        raise RuntimeError(f"Missing population values: {missing}")

    total_population = out["Population_2023"].sum()
    if total_population <= 0:
        raise RuntimeError("Population total is not positive.")
    out["Country_PopShare_2023"] = out["Population_2023"] / total_population

    residual_detail = residual_candidates[
        [
            "GLORIA_rest_code",
            "wb_code",
            "wb_name",
            "wb_region",
            "wb_income",
            "Population_2023",
        ]
    ].copy()
    residual_detail = residual_detail.sort_values(["GLORIA_rest_code", "wb_code"])

    out.to_csv(OUT_WEIGHTS, index=False)
    residual_detail.to_csv(OUT_RESIDUAL, index=False)

    print(f"Wrote {OUT_WEIGHTS}")
    print(f"Wrote {OUT_RESIDUAL}")
    print(f"Total GLORIA-mapped population {YEAR}: {total_population:,.0f}")
    print("Rest-region residual population:")
    for code in sorted(REST_CODES):
        value = residual_summary.get(code, 0.0)
        count = int((residual_detail["GLORIA_rest_code"] == code).sum())
        print(f"  {code}: {value:,.0f} across {count} residual rows")
    return 0


if __name__ == "__main__":
    sys.exit(main())
