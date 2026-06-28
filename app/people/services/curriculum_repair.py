"""Audit and repair oversized student primary-curriculum enrollments."""

from __future__ import annotations

import csv
from collections import defaultdict
from dataclasses import dataclass
from datetime import date
from pathlib import Path
import re
from typing import TypeAlias, TypedDict

from django.core.management.base import CommandError
from django.db import transaction
from django.db.models import Q
from django.utils import timezone

from app.academics.models.curriculum import Curriculum
from app.academics.models.curriculum_course import CurriCrs
from app.people.models.student import Student
from app.people.models.student_curriculum_enrollment import (
    StdCurriEnroll,
    set_primary_std_curri_enroll,
)
from app.registry.models.grade import Grade
from app.registry.models.registration import Registration

DEFAULT_MAX_CREDITS = 200
DEFAULT_LOG_DIR = Path("logs/curriculum_reconciliation")
CourseIdSetT: TypeAlias = set[int]
CurriCourseMapT: TypeAlias = dict[int, CourseIdSetT]
CreditTotalMapT: TypeAlias = dict[int, int]
STOP_TOKENS = {
    "arts",
    "ba",
    "bba",
    "bpa",
    "bs",
    "bsc",
    "cas",
    "cba",
    "cet",
    "chs",
    "curriculum",
    "degree",
    "eng",
    "engineering",
    "of",
    "program",
    "science",
    "sciences",
    "the",
}


class RepairAuditRowT(TypedDict):
    """CSV audit row for one oversized curriculum-enrollment decision."""

    student_db_id: str
    student_id: str
    username: str
    source_curriculum_id: str
    source_curriculum: str
    source_credits: str
    target_curriculum_id: str
    target_curriculum: str
    target_credits: str
    evidence_courses: str
    matched_courses: str
    action: str
    reason: str


@dataclass(frozen=True)
class CandidateMatch:
    """Candidate curriculum score for one student."""

    curriculum: Curriculum
    total_credits: int
    matched_courses: int


@dataclass(frozen=True)
class Resolution:
    """Resolved curriculum movement decision."""

    target: CandidateMatch | None
    reason: str


@dataclass(frozen=True)
class RepairRunResult:
    """Summary for an oversized-curriculum repair run."""

    applied: bool
    log_path: Path
    processed: int
    moved: int
    would_move: int
    unresolved: int

    def summary(self) -> str:
        """Return a CLI-friendly summary line."""
        mode = "Applied" if self.applied else "Dry-run"
        return (
            f"{mode} oversized curriculum repair: {self.processed} processed, "
            f"{self.moved} moved, {self.would_move} would-move, "
            f"{self.unresolved} unresolved. Audit: {self.log_path}"
        )


def repair_oversized_curriculum_enrollments(
    *,
    max_credits: int = DEFAULT_MAX_CREDITS,
    student_token: str = "",
    raw_log_path: str = "",
    apply_changes: bool = False,
) -> RepairRunResult:
    """Move deterministic oversized primary enrollments to canonical curricula."""
    max_credits = max(int(max_credits), 1)
    selected_student_id = (
        _resolve_student_id(student_token.strip()) if student_token.strip() else None
    )
    log_path = _resolve_log_path(raw_log_path.strip())
    credit_totals = _curriculum_credit_totals()
    candidates = _candidate_curricula(credit_totals, max_credits)
    candidate_course_ids = _curriculum_course_ids(
        [candidate.id for candidate in candidates]
    )
    enrollments = _oversized_primary_enrollments(
        credit_totals,
        max_credits,
        selected_student_id,
    )
    rows: list[RepairAuditRowT] = []
    moved = 0
    would_move = 0
    unresolved = 0
    for enroll in enrollments:
        evidence_ids, first_semester_id = _student_evidence(enroll.student_id)
        resolution = _resolve_target(
            enroll.curriculum,
            credit_totals,
            candidates,
            candidate_course_ids,
            evidence_ids,
        )
        target = resolution.target
        action = "unresolved"
        if target is None:
            unresolved += 1
        elif apply_changes:
            _move_primary_enrollment(
                enroll,
                target.curriculum,
                entry_semester_id=enroll.entry_semester_id or first_semester_id,
            )
            moved += 1
            action = "moved"
        else:
            would_move += 1
            action = "would_move"
        rows.append(
            _audit_row(
                enroll,
                credit_totals,
                evidence_ids,
                target,
                action,
                resolution.reason,
            )
        )
    _write_audit_rows(log_path, rows)
    return RepairRunResult(
        applied=apply_changes,
        log_path=log_path,
        processed=len(enrollments),
        moved=moved,
        would_move=would_move,
        unresolved=unresolved,
    )


def _resolve_student_id(token: str) -> int:
    """Resolve a student selector to a database id."""
    query = Q(user__username=token) | Q(username=token) | Q(student_id=token)
    if token.isdigit():
        query |= Q(id=int(token))
    student = Student.objects.filter(query).order_by("id").first()
    if student is None:
        raise CommandError(f"Student not found: {token}")
    return int(student.id)


def _resolve_log_path(raw_path: str) -> Path:
    """Return the audit CSV path for this run."""
    if raw_path:
        return Path(raw_path)
    timestamp = timezone.now().strftime("%Y%m%d_%H%M%S")
    return DEFAULT_LOG_DIR / f"oversized_curriculum_repair_{timestamp}.csv"


def _curriculum_credit_totals() -> CreditTotalMapT:
    """Return total mapped credits by curriculum id."""
    totals: CreditTotalMapT = {}
    for curriculum_id, credit_hours_id in CurriCrs.objects.values_list(
        "curriculum_id",
        "credit_hours_id",
    ):
        key = int(curriculum_id)
        totals[key] = totals.get(key, 0) + int(credit_hours_id or 0)
    return totals


def _candidate_curricula(
    credit_totals: CreditTotalMapT,
    max_credits: int,
) -> list[Curriculum]:
    """Return approved active curricula at or below the credit ceiling."""
    candidate_ids = [
        curriculum_id
        for curriculum_id, total in credit_totals.items()
        if 0 < total <= max_credits
    ]
    return list(
        Curriculum.objects.filter(
            id__in=candidate_ids,
            status_id="approved",
            is_active=True,
        ).select_related("college")
    )


def _curriculum_course_ids(curriculum_ids: list[int]) -> CurriCourseMapT:
    """Return course-id sets by curriculum id."""
    course_ids: CurriCourseMapT = defaultdict(set)
    if not curriculum_ids:
        return {}
    for curriculum_id, course_id in CurriCrs.objects.filter(
        curriculum_id__in=curriculum_ids
    ).values_list("curriculum_id", "course_id"):
        course_ids[int(curriculum_id)].add(int(course_id))
    return dict(course_ids)


def _oversized_primary_enrollments(
    credit_totals: CreditTotalMapT,
    max_credits: int,
    student_id: int | None,
) -> list[StdCurriEnroll]:
    """Return primary enrollments attached to curricula over the credit ceiling."""
    oversized_ids = [
        curriculum_id
        for curriculum_id, total in credit_totals.items()
        if total > max_credits
    ]
    qs = StdCurriEnroll.objects.filter(
        is_primary=True,
        curriculum_id__in=oversized_ids,
    ).select_related("student", "student__user", "curriculum", "curriculum__college")
    if student_id is not None:
        qs = qs.filter(student_id=student_id)
    return list(qs.order_by("student__student_id", "student__user__username", "id"))


def _student_evidence(student_id: int) -> tuple[CourseIdSetT, int | None]:
    """Return course evidence and earliest semester id from grades/registrations."""
    course_ids: CourseIdSetT = set()
    semester_pairs: list[tuple[date, int]] = []
    registration_rows = Registration.objects.filter(student_id=student_id).values_list(
        "section__curriculum_course__course_id",
        "section__semester__start_date",
        "section__semester_id",
    )
    grade_rows = Grade.objects.filter(student_id=student_id).values_list(
        "section__curriculum_course__course_id",
        "section__semester__start_date",
        "section__semester_id",
    )
    for course_id, start_date, semester_id in list(registration_rows) + list(grade_rows):
        if course_id:
            course_ids.add(int(course_id))
        if start_date and semester_id:
            semester_pairs.append((start_date, int(semester_id)))
    semester_pairs.sort(key=lambda pair: pair[0])
    first_semester_id = semester_pairs[0][1] if semester_pairs else None
    return course_ids, first_semester_id


def _resolve_target(
    source: Curriculum,
    credit_totals: CreditTotalMapT,
    candidates: list[Curriculum],
    candidate_course_ids: CurriCourseMapT,
    evidence_ids: CourseIdSetT,
) -> Resolution:
    """Resolve one deterministic target curriculum from evidence."""
    if not evidence_ids:
        return Resolution(None, "no_registration_or_grade_evidence")
    matches: list[CandidateMatch] = []
    for candidate in candidates:
        if candidate.college_id != source.college_id:
            continue
        matched_courses = len(
            evidence_ids.intersection(candidate_course_ids.get(int(candidate.id), set()))
        )
        if matched_courses and not _program_family_matches(source, candidate):
            continue
        if matched_courses:
            matches.append(
                CandidateMatch(
                    curriculum=candidate,
                    total_credits=credit_totals.get(int(candidate.id), 0),
                    matched_courses=matched_courses,
                )
            )
    if not matches:
        return Resolution(None, "no_same_college_program_family_match")
    matches.sort(
        key=lambda match: (
            match.matched_courses,
            -match.total_credits,
            -(match.curriculum.id or 0),
        ),
        reverse=True,
    )
    winner = matches[0]
    second_score = matches[1].matched_courses if len(matches) > 1 else 0
    if winner.matched_courses == second_score:
        return Resolution(None, "ambiguous_top_match")
    if winner.matched_courses * 2 <= len(evidence_ids):
        return Resolution(None, "no_majority_evidence_match")
    return Resolution(winner, "approved_active_majority_evidence_match")


def _program_family_matches(source: Curriculum, candidate: Curriculum) -> bool:
    """Return whether source and target names share a meaningful program token."""
    return bool(_program_tokens(source).intersection(_program_tokens(candidate)))


def _program_tokens(curriculum: Curriculum) -> set[str]:
    """Return normalized non-generic tokens from a curriculum name."""
    raw_text = f"{curriculum.short_name} {curriculum.long_name or ''}".lower()
    tokens: set[str] = set()
    for token in re.findall(r"[a-z0-9]+", raw_text):
        normalized = _normalize_program_token(token)
        if normalized:
            tokens.add(normalized)
    return tokens


def _normalize_program_token(token: str) -> str:
    """Normalize common abbreviations while dropping generic degree words."""
    if token in STOP_TOKENS or len(token) < 3:
        return ""
    if token.startswith("elec"):
        return "elec"
    if token.startswith("civ"):
        return "civi"
    if token.startswith("env"):
        return "env"
    if token.startswith("fren"):
        return "fren"
    if token.startswith("bio"):
        return "bio"
    if token.startswith("acct") or token.startswith("account"):
        return "acct"
    if token.startswith("manage"):
        return "management"
    return token


def _move_primary_enrollment(
    enroll: StdCurriEnroll,
    target: Curriculum,
    *,
    entry_semester_id: int | None,
) -> None:
    """Persist a deterministic primary-curriculum move."""
    with transaction.atomic():
        set_primary_std_curri_enroll(
            enroll.student,
            target,
            entry_semester_id=entry_semester_id,
            is_active=True,
        )
        StdCurriEnroll.objects.filter(pk=enroll.pk).exclude(curriculum=target).update(
            is_active=False
        )


def _audit_row(
    enroll: StdCurriEnroll,
    credit_totals: CreditTotalMapT,
    evidence_ids: CourseIdSetT,
    target: CandidateMatch | None,
    action: str,
    reason: str,
) -> RepairAuditRowT:
    """Build one oversized-curriculum repair audit row."""
    student = enroll.student
    target_curriculum = target.curriculum if target else None
    return {
        "student_db_id": str(student.id),
        "student_id": student.student_id or "",
        "username": student.user.username if student.user_id else student.username,
        "source_curriculum_id": str(enroll.curriculum_id),
        "source_curriculum": str(enroll.curriculum),
        "source_credits": str(credit_totals.get(int(enroll.curriculum_id), 0)),
        "target_curriculum_id": str(target_curriculum.id if target_curriculum else ""),
        "target_curriculum": str(target_curriculum or ""),
        "target_credits": str(target.total_credits if target else ""),
        "evidence_courses": str(len(evidence_ids)),
        "matched_courses": str(target.matched_courses if target else ""),
        "action": action,
        "reason": reason,
    }


def _write_audit_rows(path: Path, rows: list[RepairAuditRowT]) -> None:
    """Write oversized-curriculum repair audit rows."""
    path.parent.mkdir(parents=True, exist_ok=True)
    headers = list(RepairAuditRowT.__annotations__)
    with path.open("w", encoding="utf-8", newline="") as handle:
        writer = csv.DictWriter(handle, fieldnames=headers)
        writer.writeheader()
        writer.writerows(rows)


__all__ = [
    "DEFAULT_MAX_CREDITS",
    "RepairRunResult",
    "repair_oversized_curriculum_enrollments",
]
