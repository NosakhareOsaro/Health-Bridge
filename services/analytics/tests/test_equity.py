"""Tests for the synthetic health-equity region generator."""

from __future__ import annotations

from equity.generate_equity_data import GRID_SIZE, generate_regions


def test_generate_regions_produces_full_grid():
    regions = generate_regions()
    assert len(regions) == GRID_SIZE * GRID_SIZE
    assert regions["region_id"].is_unique


def test_generate_regions_metrics_are_in_plausible_ranges():
    regions = generate_regions()
    assert (regions["deprivation_index"].between(1, 10)).all()
    assert (regions["diabetes_prevalence_pct"] > 0).all()
    assert (regions["life_expectancy_years"].between(50, 90)).all()
    assert (regions["population"] > 0).all()


def test_generate_regions_is_deterministic_for_a_given_seed():
    a = generate_regions(seed=3)
    b = generate_regions(seed=3)
    assert a.drop(columns="geometry").equals(b.drop(columns="geometry"))


def test_generate_regions_geometries_are_valid_polygons():
    regions = generate_regions()
    assert (regions.geometry.is_valid).all()
    assert regions.crs.to_string() == "EPSG:4326"
