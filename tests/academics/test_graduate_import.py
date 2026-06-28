"""Graduate curriculum import command regressions."""

from __future__ import annotations

import csv
from pathlib import Path

import pytest
from django.core.management import call_command

pytestmark = pytest.mark.django_db


def _read_tsv(path: Path) -> list[dict[str, str]]:
    """Read a TSV file into dictionaries."""
    with path.open("r", encoding="utf-8", newline="") as handle:
        return list(csv.DictReader(handle, delimiter="\t"))


def _write_graduate_source(path: Path) -> None:
    """Create a minimal graduate Org source with one valid and one rejected program."""
    path.write_text(
        r"""
* Master Degree and Postgraduate Programs
\TUCNewGlo{grad-mbam}{Curriculum for Master of Business Administration in Management}
\TUCNewGlo{grad-msgh}{Curriculum for Master of Science in Global Health}
\TUCNewGlo{grad-clim}{Incomplete Graduate Climate Program}

** Curriculum for Master of Business Administration in Management
*** Curriculum
**** Year Plan 1
#+BEGIN_EXPORT latex
% BEGIN RECEIVE ORGTBL grad-mbam-t1
\TUCTblAnchor{tbl:grad-mbam-t1}
\begin{TUTblSem6X}{\textwidth}
MBAD 609 & \truncate{\TUCTSemTitleW}{Research Methods} & 4 & MBAD 602 & \truncate{\TUCTSemTitleW}{Statistical Methods in Research} & 4\\
\midrule
\multicolumn{2}{l}{\textbf{Semester I TOTAL}} & \textbf{4} & \multicolumn{2}{l}{\textbf{Semester II TOTAL}} & \textbf{4}\\
\end{TUTblSem6X}
% END RECEIVE ORGTBL grad-mbam-t1
#+END_EXPORT

** Curriculum for Master of Science in Global Health
*** Curriculum
**** Year Plan 1
#+BEGIN_EXPORT latex
% BEGIN RECEIVE ORGTBL grad-msgh-t1
\TUCTblAnchor{tbl:grad-msgh-t1}
\begin{TUTblSem6X}{\textwidth}
MSGH 501 & \truncate{\TUCTSemTitleW}{Foundations of Global Health} & 3 & MSGH 601 & \truncate{\TUCTSemTitleW}{Global Health Leadership} & 3\\
\midrule
\multicolumn{2}{l}{\textbf{Semester I TOTAL}} & \textbf{3} & \multicolumn{2}{l}{\textbf{Semester II TOTAL}} & \textbf{3}\\
\end{TUTblSem6X}
% END RECEIVE ORGTBL grad-msgh-t1
#+END_EXPORT

** Incomplete Graduate Climate Program
*** Curriculum
No official curriculum table is available yet.

* Course Descriptions

** Curriculum for Master of Business Administration in Management
#+BEGIN_EXPORT latex
\TUCSetCrsGloT{grad-mbam}
\TUCCrsDescDef[][]{mbad609}{MBAD 609}{Research Methods}{4 credits}{Graduate research design.}
\TUCCrsDescDef[MBAD 609][]{mbad602}{MBAD 602}{Statistical Methods in Research}{4 credits}{Graduate statistics.}
\TUPrintCrsGlo{grad-mbam}
#+END_EXPORT

** Curriculum for Master of Science in Global Health
#+BEGIN_EXPORT latex
\TUCSetCrsGloT{grad-msgh}
\TUCCrsDescDef[][]{msgh501}{MSGH 501}{Foundations of Global Health}{3 credits}{Global health foundations.}
\TUCCrsDescDef[][]{msgh601}{MSGH 601}{Global Health Leadership}{3 credits}{Graduate leadership.}
\TUPrintCrsGlo{grad-msgh}
#+END_EXPORT
""",
        encoding="utf-8",
    )


def test_build_graduate_import_writes_valid_rows_and_reject_reports(tmp_path) -> None:
    """Graduate importer should keep valid rows and produce stable reject TSVs."""
    source = tmp_path / "graduate.org"
    output_dir = tmp_path / "graduate_import"
    _write_graduate_source(source)

    call_command(
        "build_graduate_import",
        "--source",
        str(source),
        "--output-dir",
        str(output_dir),
    )

    curricula = _read_tsv(output_dir / "academic_curriculum.tsv")
    curriculum_courses = _read_tsv(output_dir / "academic_curriculum_course.tsv")
    requirements = _read_tsv(output_dir / "academic_curriculum_requirement.tsv")
    rejected = _read_tsv(output_dir / "rejected_curricula.tsv")
    summary = (output_dir / "SUMMARY.txt").read_text(encoding="utf-8")

    assert [row["curriculum"] for row in curricula] == ["GRAD-MBAM", "GRAD-MSGH"]
    assert {row["academic_career"] for row in curricula} == {"graduate"}
    assert {
        (row["curriculum"], row["course_dept"], row["course_no"])
        for row in curriculum_courses
    } >= {("GRAD-MSGH", "MSGH", "501"), ("GRAD-MSGH", "MSGH", "601")}
    assert {row["is_elective"] for row in curriculum_courses} == {"false"}
    assert {
        (row["course_dept"], row["course_no"], row["required_course_dept"])
        for row in requirements
    } == {("MBAD", "602", "MBAD")}
    assert any(
        row["source_slug"] == "grad-clim" and row["reason"] == "missing_curriculum_rows"
        for row in rejected
    )
    assert "valid_curricula: 2" in summary
