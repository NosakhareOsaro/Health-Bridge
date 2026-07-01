#!/usr/bin/env python3
"""Generate SYNTHETIC health-equity metrics for a small grid of fictional service areas.

There are no real ZIP Code Tabulation Area (ZCTA) boundary files bundled with
this project (downloading the real US Census TIGER/Line shapefiles is out of
scope for a portfolio ETL), so this script fabricates a small grid of square
polygons around the Boston, MA area (where the Synthea population in this
project is also generated) and assigns each a synthetic deprivation index,
chronic disease prevalence, and life-expectancy estimate. Do not treat this
as real geographic or demographic data.

Usage:
    python equity/generate_equity_data.py --output data/equity_regions.geojson
"""

from __future__ import annotations

import argparse
from pathlib import Path

import geopandas as gpd
import numpy as np
from shapely.geometry import box

# Roughly centered on Boston, MA -- consistent with the Synthea population
# this project generates, purely for a plausible-looking map extent.
CENTER_LAT, CENTER_LON = 42.36, -71.06
GRID_SIZE = 5  # 5x5 grid of synthetic "service areas"
CELL_DEGREES = 0.08


def generate_regions(seed: int = 7) -> gpd.GeoDataFrame:
    rng = np.random.default_rng(seed)
    records = []

    for row in range(GRID_SIZE):
        for col in range(GRID_SIZE):
            min_lon = CENTER_LON + (col - GRID_SIZE / 2) * CELL_DEGREES
            min_lat = CENTER_LAT + (row - GRID_SIZE / 2) * CELL_DEGREES
            geom = box(min_lon, min_lat, min_lon + CELL_DEGREES, min_lat + CELL_DEGREES)

            deprivation_index = round(float(rng.uniform(1, 10)), 1)
            # Higher deprivation correlates with higher chronic disease
            # prevalence and lower life expectancy, plus noise -- a
            # plausible (not real) social-determinants-of-health pattern.
            diabetes_prevalence_pct = round(
                max(2.0, 4 + deprivation_index * 1.1 + rng.normal(0, 1.5)), 1
            )
            life_expectancy_years = round(
                min(90, 84 - deprivation_index * 0.9 + rng.normal(0, 1.2)), 1
            )
            population = int(rng.integers(2_000, 25_000))

            records.append(
                {
                    "region_id": f"R{row}{col}",
                    "deprivation_index": deprivation_index,
                    "diabetes_prevalence_pct": diabetes_prevalence_pct,
                    "life_expectancy_years": life_expectancy_years,
                    "population": population,
                    "geometry": geom,
                }
            )

    return gpd.GeoDataFrame(records, crs="EPSG:4326")


def main() -> None:
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument(
        "--output",
        type=Path,
        default=Path(__file__).resolve().parent / "data" / "equity_regions.geojson",
    )
    parser.add_argument("--seed", type=int, default=7)
    args = parser.parse_args()

    gdf = generate_regions(seed=args.seed)
    args.output.parent.mkdir(parents=True, exist_ok=True)
    gdf.to_file(args.output, driver="GeoJSON")
    print(f"Wrote {len(gdf)} synthetic regions to {args.output}")


if __name__ == "__main__":
    main()
