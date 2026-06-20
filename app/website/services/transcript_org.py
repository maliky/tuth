"""Org-mode source rendering for registrar transcript documents."""

from __future__ import annotations

from typing import TypeAlias

from app.website.services.transcript_types import TranscriptDocumentT

LatexValueListT: TypeAlias = list[str]

LATEX_ESCAPE_MAP: dict[str, str] = {
    "\\": r"\textbackslash{}",
    "&": r"\&",
    "%": r"\%",
    "$": r"\$",
    "#": r"\#",
    "_": r"\_",
    "{": r"\{",
    "}": r"\}",
    "~": r"\textasciitilde{}",
    "^": r"\textasciicircum{}",
}


def latex_escape(value: str) -> str:
    """Return text escaped for safe use inside simple LaTeX macro arguments."""
    return "".join(LATEX_ESCAPE_MAP.get(char, char) for char in value)


def _latex_command(name: str, values: LatexValueListT) -> str:
    """Return a LaTeX command with escaped braced arguments."""
    args = "".join(f"{{{latex_escape(value)}}}" for value in values)
    return f"\\{name}{args}"


def _latex_header_command(name: str, value: str) -> str:
    """Return an Org LaTeX header line renewing a transcript macro."""
    return f"#+LATEX_HEADER: \\renewcommand{{\\{name}}}{{{latex_escape(value)}}}"


def _transcript_header_lines(document: TranscriptDocumentT) -> list[str]:
    """Return Org metadata and LaTeX header commands for the transcript."""
    macros = [
        ("TUTranscriptLogoFile", "logo120pi.png"),
        ("TUTranscriptInstitutionName", document["institution_name"]),
        ("TUTranscriptAddressOne", document["address_one"]),
        ("TUTranscriptAddressTwo", document["address_two"]),
        ("TUTranscriptCountry", document["country"]),
        ("TUTranscriptWebsite", document["website"]),
        ("TUTranscriptRegistrarEmail", document["registrar_email"]),
        ("TUTranscriptDocumentTitle", document["document_title"]),
        ("TUTranscriptDraftLabel", ""),
        ("TUTranscriptStudentName", document["student_name"]),
        ("TUTranscriptStudentAddressOne", document["student_address_one"]),
        ("TUTranscriptStudentAddressTwo", document["student_address_two"]),
        ("TUTranscriptStudentID", document["student_id"]),
        ("TUTranscriptDOB", document["dob"]),
        ("TUTranscriptCollege", document["college"]),
        ("TUTranscriptProgramCode", document["program_code"]),
        ("TUTranscriptProgramName", document["major_program"]),
        ("TUTranscriptMajorProgram", document["major_program"]),
        ("TUTranscriptEnrollmentDate", document["enrollment_date"]),
        ("TUTranscriptCompletionDate", document["completion_date"]),
        ("TUTranscriptGraduationDate", document["graduation_date"]),
        ("TUTranscriptProgramTotalAttempted", document["program_total_attempted"]),
        ("TUTranscriptProgramTotalEarned", document["program_total_earned"]),
        ("TUTranscriptProgramTotalGPA", document["program_total_gpa"]),
        ("TUTranscriptCumulativeTotalAttempted", document["cumulative_total_attempted"]),
        ("TUTranscriptCumulativeTotalEarned", document["cumulative_total_earned"]),
        ("TUTranscriptCumulativeTotalGPA", document["cumulative_total_gpa"]),
        ("TUTranscriptPrintedDate", document["printed_date"]),
        ("TUTranscriptPrintedDateShort", document["printed_date_short"]),
        ("TUTranscriptGradeLegend", document["grade_legend"]),
        ("TUTranscriptGradePolicyIntro", document["grade_policy_intro"]),
        ("TUTranscriptMentionRulesNote", document["mention_rules_note"]),
        ("TUTranscriptNoticeFinal", document["notice_final"]),
        ("TUTranscriptRegistrarTitle", document["registrar_title"]),
    ]
    lines = [
        f"#+TITLE: Transcript - {document['student_id']}",
        "#+AUTHOR: Office of the Registrar",
        f"#+DATE: {document['printed_date']}",
        "#+LATEX_CLASS: tutranscript",
        "#+LATEX_CLASS_OPTIONS: [10pt,a4paper]",
        "#+LATEX_COMPILER: lualatex",
        "#+OPTIONS: toc:nil title:nil author:nil date:nil ^:nil",
        "#+EXPORT_FILE_NAME: transcript",
        "",
    ]
    lines.extend(_latex_header_command(name, value) for name, value in macros)
    return lines


def _transcript_detail_lines(document: TranscriptDocumentT) -> list[str]:
    """Return LaTeX transcript detail macros generated from term groups."""
    lines = [
        _latex_command(
            "TUTranscriptProgramRow",
            [document["program_code"], document["major_program"]],
        )
    ]
    has_rows = False
    for group in document["term_groups"]:
        lines.append(
            _latex_command(
                "TUTranscriptTermHeader",
                [group["term_label"]],
            )
        )
        for row in group["rows"]:
            has_rows = True
            lines.append(
                _latex_command(
                    "TUTranscriptCourse",
                    [
                        row["course_code"],
                        row["course_title"],
                        row["final_grade"],
                        row["attempted_credit"],
                        row["earned_credit"],
                        row["quality_points"],
                    ],
                )
            )
        lines.append(
            _latex_command(
                "TUTranscriptTotals",
                [
                    "Term Totals",
                    group["term_gpa"],
                    group["term_attempted_credit"],
                    group["term_earned_credit"],
                    group["term_quality_points"],
                ],
            )
        )
        lines.append(
            _latex_command(
                "TUTranscriptTotals",
                [
                    "Program Totals",
                    group["program_gpa"],
                    group["program_attempted_credit"],
                    group["program_earned_credit"],
                    group["program_quality_points"],
                ],
            )
        )
    if not has_rows:
        lines.append(_latex_command("TUTranscriptEmptyRow", ["No grades recorded."]))
    return lines


def render_transcript_document_org(document: TranscriptDocumentT) -> str:
    """Render a standalone Org source file for a transcript export."""
    lines = _transcript_header_lines(document)
    lines.extend(
        [
            "",
            "* Transcript Source",
            "This source is intended for export with the bundled tutranscript class.",
            "",
            "#+begin_export latex",
            "\\renewcommand{\\TUTranscriptDetailRows}{%",
        ]
    )
    lines.extend(f"  {line}" for line in _transcript_detail_lines(document))
    lines.extend(
        [
            "}",
            "\\TUPrintTranscript",
            "#+end_export",
            "",
        ]
    )
    return "\n".join(lines)


__all__ = [
    "latex_escape",
    "render_transcript_document_org",
]
