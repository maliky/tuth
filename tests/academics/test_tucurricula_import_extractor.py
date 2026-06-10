"""Tests for the tucurricula Org-to-TUSIS import extractor."""

from __future__ import annotations

import csv
from pathlib import Path

from scripts.extract_tucurricula_imports import extract


def _read_tsv(path: Path) -> list[dict[str, str]]:
    """Read a TSV file into dictionaries."""
    with path.open("r", encoding="utf-8", newline="") as handle:
        return list(csv.DictReader(handle, delimiter="\t"))


def _write_source_root(root: Path) -> None:
    """Create a minimal tucurricula-like source tree."""
    audit_dir = root / "Audit"
    audit_dir.mkdir()
    (audit_dir / "programs.org").write_text(
        "| College / Unit | Slug | Program |\n"
        "|-\n"
        "| cas | phys | Bachelor of Science in Physics |\n",
        encoding="utf-8",
    )
    (audit_dir / "tu_audit.py").write_text(
        "import pandas as pd\n"
        "DEFAULT_FILES = ['cas_curriculum_2025.org']\n"
        "def extract_program_tables(root_dir):\n"
        "    return pd.DataFrame([\n"
        "        {'code': 'MATH 101', 'title': 'College Algebra', 'credit': 3, 'semester': 1, 'year': 1, 'program': 'Bachelor of Science in Physics', 'college': 'cas'},\n"
        "        {'code': 'PHYS 101', 'title': 'Physics I', 'credit': 4, 'semester': 1, 'year': 1, 'program': 'Bachelor of Science in Physics', 'college': 'cas'},\n"
        "        {'code': 'PHYS 102', 'title': 'Physics II', 'credit': 4, 'semester': 2, 'year': 1, 'program': 'Bachelor of Science in Physics', 'college': 'cas'},\n"
        "    ])\n",
        encoding="utf-8",
    )
    (root / "cas_curriculum_2025.org").write_text(
        r"""
\TUCCrsDescDef{math101}{MATH 101}{College Algebra}{3 credits}{Algebra foundations.}
\TUCCrsDescDef{phys101}{PHYS 101}{Physics I}{4 credits}{Mechanics.}
\TUCCrsDescDef[\gls{math101}][\gls{phys101}]{phys102}{PHYS 102}{Physics II}{4 credits}{Electricity {and magnetism} with \gls{math101}.}
""",
        encoding="utf-8",
    )


def test_extract_tucurricula_imports_writes_courses_and_requirements(tmp_path) -> None:
    """Extractor should emit import TSVs and resolvable grouped requirements."""
    source_root = tmp_path / "tucurricula"
    source_root.mkdir()
    output_dir = tmp_path / "out"
    _write_source_root(source_root)

    extract(source_root, output_dir)

    curricula = _read_tsv(output_dir / "academic_curriculum.tsv")
    courses = _read_tsv(output_dir / "academic_course.tsv")
    curriculum_courses = _read_tsv(output_dir / "academic_curriculum_course.tsv")
    requirements = _read_tsv(output_dir / "academic_curriculum_requirement.tsv")
    unresolved = _read_tsv(output_dir / "unresolved_requisites.tsv")

    assert curricula[0]["curriculum"] == "CAS-PHYS"
    assert curricula[0]["long_name"] == "Bachelor of Science in Physics"
    phys_102 = next(row for row in courses if row["source_course_key"] == "PHYS102")
    assert phys_102["course_dept"] == "PHYS"
    assert phys_102["course_no"] == "102"
    assert "Electricity and magnetism" in phys_102["description"]
    assert any(row["level_number"] == "2" for row in curriculum_courses)
    assert {row["requirement_kind"] for row in requirements} == {
        "prereq_all",
        "coreq_all",
    }
    assert {row["required_course_dept"] for row in requirements} == {"MATH", "PHYS"}
    assert unresolved == []
