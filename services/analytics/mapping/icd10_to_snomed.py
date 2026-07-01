#!/usr/bin/env python3
"""ICD-10-CM -> SNOMED CT concept mapping utility.

Queries the OMOP CDM vocabulary tables (``cdm.concept`` /
``cdm.concept_relationship``) built by ``services/etl`` to resolve an
ICD-10-CM code to its mapped standard SNOMED CT concept, following the same
"Maps to" relationship the dbt ETL uses internally
(``services/etl/dbt_omop/models/omop/condition_occurrence.sql``). This is a
standalone, reusable utility for analysts who just need a code translated,
independent of the ETL run.

Usage:
    python mapping/icd10_to_snomed.py J01.90
    python mapping/icd10_to_snomed.py --batch codes.csv --output mapped.csv
    python mapping/icd10_to_snomed.py --all   # dump the full seeded crosswalk
"""

from __future__ import annotations

import argparse
import csv
import os
import sys
from dataclasses import dataclass

from sqlalchemy import create_engine, text
from sqlalchemy.engine import Engine

OMOP_DB_URL = os.environ.get("OMOP_DB_URL", "postgresql://omop:omop@localhost:5434/omop")


@dataclass
class MappingResult:
    icd10_code: str
    icd10_display: str | None
    snomed_code: str | None
    snomed_display: str | None
    mapped: bool


def get_engine(db_url: str | None = None) -> Engine:
    return create_engine(db_url or OMOP_DB_URL)


def map_icd10_to_snomed(engine: Engine, icd10_code: str) -> MappingResult:
    query = text(
        """
        select
            src.concept_code as icd10_code,
            src.concept_name as icd10_display,
            tgt.concept_code as snomed_code,
            tgt.concept_name as snomed_display
        from cdm.concept src
        left join cdm.concept_relationship rel
            on rel.concept_id_1 = src.concept_id and rel.relationship_id = 'Maps to'
        left join cdm.concept tgt
            on tgt.concept_id = rel.concept_id_2 and tgt.vocabulary_id = 'SNOMED'
        where src.vocabulary_id = 'ICD10CM' and src.concept_code = :code
        """
    )
    with engine.connect() as conn:
        row = conn.execute(query, {"code": icd10_code}).mappings().first()

    if row is None:
        return MappingResult(icd10_code, None, None, None, mapped=False)
    return MappingResult(
        icd10_code=row["icd10_code"],
        icd10_display=row["icd10_display"],
        snomed_code=row["snomed_code"],
        snomed_display=row["snomed_display"],
        mapped=row["snomed_code"] is not None,
    )


def map_batch(engine: Engine, icd10_codes: list[str]) -> list[MappingResult]:
    return [map_icd10_to_snomed(engine, code) for code in icd10_codes]


def dump_full_crosswalk(engine: Engine) -> list[MappingResult]:
    query = text(
        """
        select
            src.concept_code as icd10_code,
            src.concept_name as icd10_display,
            tgt.concept_code as snomed_code,
            tgt.concept_name as snomed_display
        from cdm.concept src
        left join cdm.concept_relationship rel
            on rel.concept_id_1 = src.concept_id and rel.relationship_id = 'Maps to'
        left join cdm.concept tgt
            on tgt.concept_id = rel.concept_id_2 and tgt.vocabulary_id = 'SNOMED'
        where src.vocabulary_id = 'ICD10CM'
        order by src.concept_code
        """
    )
    with engine.connect() as conn:
        rows = conn.execute(query).mappings().all()
    return [
        MappingResult(
            icd10_code=r["icd10_code"],
            icd10_display=r["icd10_display"],
            snomed_code=r["snomed_code"],
            snomed_display=r["snomed_display"],
            mapped=r["snomed_code"] is not None,
        )
        for r in rows
    ]


def _print_result(result: MappingResult) -> None:
    if result.mapped:
        print(f"{result.icd10_code} ({result.icd10_display})  ->  {result.snomed_code} ({result.snomed_display})")
    else:
        print(f"{result.icd10_code}: no SNOMED mapping found in the loaded vocabulary subset")


def main() -> int:
    parser = argparse.ArgumentParser(description=__doc__, formatter_class=argparse.RawDescriptionHelpFormatter)
    parser.add_argument("code", nargs="?", help="A single ICD-10-CM code to map, e.g. J01.90")
    parser.add_argument("--batch", type=argparse.FileType("r"), help="CSV file with an icd10_code column")
    parser.add_argument("--output", type=argparse.FileType("w"), help="Where to write batch results as CSV")
    parser.add_argument("--all", action="store_true", help="Dump the full seeded ICD10CM->SNOMED crosswalk")
    parser.add_argument("--database-url", default=None, help="Override OMOP_DB_URL")
    args = parser.parse_args()

    engine = get_engine(args.database_url)

    if args.all:
        results = dump_full_crosswalk(engine)
        for r in results:
            _print_result(r)
        return 0

    if args.batch:
        reader = csv.DictReader(args.batch)
        codes = [row["icd10_code"] for row in reader]
        results = map_batch(engine, codes)
        if args.output:
            writer = csv.writer(args.output)
            writer.writerow(["icd10_code", "icd10_display", "snomed_code", "snomed_display", "mapped"])
            for r in results:
                writer.writerow([r.icd10_code, r.icd10_display, r.snomed_code, r.snomed_display, r.mapped])
        else:
            for r in results:
                _print_result(r)
        return 0

    if not args.code:
        parser.print_help()
        return 1

    _print_result(map_icd10_to_snomed(engine, args.code))
    return 0


if __name__ == "__main__":
    sys.exit(main())
