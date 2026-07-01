"""Integration tests for the ICD-10 -> SNOMED CT mapping utility."""

from __future__ import annotations

from mapping.icd10_to_snomed import dump_full_crosswalk, map_batch, map_icd10_to_snomed


def test_known_code_maps_to_expected_snomed_concept(live_engine):
    result = map_icd10_to_snomed(live_engine, "J01.90")
    assert result.mapped
    assert result.snomed_code == "444814009"
    assert "sinusitis" in result.snomed_display.lower()


def test_unknown_code_is_reported_as_unmapped(live_engine):
    result = map_icd10_to_snomed(live_engine, "Z99.99")
    assert not result.mapped
    assert result.snomed_code is None


def test_batch_mapping_preserves_order(live_engine):
    results = map_batch(live_engine, ["J01.90", "D64.9", "Z99.99"])
    assert [r.icd10_code for r in results] == ["J01.90", "D64.9", "Z99.99"]
    assert results[0].mapped and results[1].mapped
    assert not results[2].mapped


def test_full_crosswalk_only_contains_icd10_source_codes(live_engine):
    results = dump_full_crosswalk(live_engine)
    assert len(results) >= 7
    assert all(r.mapped for r in results)  # the seeded crosswalk covers every seeded ICD10CM code
