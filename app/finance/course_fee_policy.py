"""Course billing policy for tuition floors and explicit fee overrides."""

from __future__ import annotations

import csv
from dataclasses import dataclass
from decimal import Decimal, InvalidOperation, ROUND_HALF_UP
from functools import lru_cache
from pathlib import Path
from typing import TYPE_CHECKING, Iterable, TypeAlias, TypedDict

from app.shared.course_wrangling import course_key
from app.timetable.utils import normalize_academic_year

if TYPE_CHECKING:
    from app.academics.models.course import Course
    from app.academics.models.curriculum_course import CurriCrs
    from app.registry.models.registration import Registration
    from app.timetable.models.semester import Semester

MoneyT: TypeAlias = Decimal
CourseFeeOverrideMapT: TypeAlias = dict[str, "CourseFeeOverrideT"]
TuitionRateMapT: TypeAlias = dict[tuple[str, int], MoneyT]

DEFAULT_TUITION_RATE_PER_CREDIT = Decimal("5.00")
MIN_COURSE_AMOUNT = Decimal("15.00")
GENERAL_SCIENCE_AMOUNT = Decimal("15.00")
DEFAULT_COURSE_FEE_OVERRIDES_PATH = Path("data/course_fees/course_fee_overrides.tsv")
DEFAULT_TUITION_RATES_PATH = Path("data/course_fees/tuition_rates.tsv")
GENERAL_SCIENCE_DEPTS = frozenset({"BIO", "BIOL", "CHEM", "CHM", "PHY", "PHYS"})
GENERAL_SCIENCE_NUMBERS = frozenset({"101", "102", "201", "202"})


class CourseFeeBreakdownT(TypedDict):
    """Computed course-fee policy details for one curriculum course."""

    course_key: str
    credit_hours: int
    tuition_rate: MoneyT
    base_amount: MoneyT
    extra_amount: MoneyT
    total_amount: MoneyT
    reason: str


class LabFeeCandidateT(TypedDict):
    """Audit row for a likely lab course without an explicit extra-fee amount."""

    course_key: str
    course_code: str
    course_title: str
    credit_hours: str
    computed_amount: str
    registration_count: str
    reason: str


@dataclass(frozen=True)
class CourseFeeOverrideT:
    """Configured course-specific base and extra fee amounts."""

    course_key: str
    base_amount: MoneyT | None
    extra_amount: MoneyT
    fee_type_code: str
    reason: str


def course_fee_breakdown(
    curriculum_course: "CurriCrs",
    semester: "Semester | None" = None,
) -> CourseFeeBreakdownT:
    """Return the billing-policy amount for one curriculum course."""
    course = curriculum_course.course
    key = course_key_for_course(course)
    credit_hours = _credit_hours(curriculum_course)
    tuition_rate = tuition_rate_for_semester(semester)
    override = course_fee_override_for(course)
    if override and override.base_amount is not None:
        base_amount = override.base_amount
        reason = "course_base_override"
    elif is_general_science_course(course):
        base_amount = GENERAL_SCIENCE_AMOUNT
        reason = "general_science_flat_amount"
    else:
        base_amount = max(Decimal(credit_hours) * tuition_rate, MIN_COURSE_AMOUNT)
        reason = "credit_rate_with_minimum"
    extra_amount = override.extra_amount if override else Decimal("0.00")
    total_amount = _money(base_amount + extra_amount)
    return {
        "course_key": key,
        "credit_hours": credit_hours,
        "tuition_rate": tuition_rate,
        "base_amount": _money(base_amount),
        "extra_amount": _money(extra_amount),
        "total_amount": total_amount,
        "reason": reason,
    }


def course_tuition_amount(
    curriculum_course: "CurriCrs",
    semester: "Semester | None" = None,
) -> MoneyT:
    """Return the base tuition amount after minimum/override policy."""
    return course_fee_breakdown(curriculum_course, semester)["base_amount"]


def course_policy_extra_amount(course: "Course") -> MoneyT:
    """Return explicit extra fee configured outside reusable fee stacks."""
    override = course_fee_override_for(course)
    return override.extra_amount if override else Decimal("0.00")


def course_fee_override_for(course: "Course") -> CourseFeeOverrideT | None:
    """Return a configured course fee override for the given course."""
    return load_course_fee_overrides().get(course_key_for_course(course))


def tuition_rate_for_semester(semester: "Semester | None") -> MoneyT:
    """Return the SmartSchool tuition rate for the semester, or the default rate."""
    if semester is None:
        return DEFAULT_TUITION_RATE_PER_CREDIT
    academic_year = normalize_academic_year(getattr(semester.academic_year, "code", ""))
    semester_number = int(getattr(semester, "number", 0) or 0)
    return load_tuition_rates().get(
        (academic_year, semester_number),
        DEFAULT_TUITION_RATE_PER_CREDIT,
    )


def is_general_science_course(course: "Course") -> bool:
    """Return True for general CHEM/BIO/PHYS 101/102/201/202 courses."""
    dept = (getattr(course.department, "code", "") or "").upper()
    number = (getattr(course, "number", "") or "").upper().replace(" ", "")
    return dept in GENERAL_SCIENCE_DEPTS and number in GENERAL_SCIENCE_NUMBERS


def unresolved_lab_fee_candidate_rows(
    registrations: Iterable["Registration"],
) -> list[LabFeeCandidateT]:
    """Return non-general 4-credit registered courses needing explicit lab fees."""
    grouped: dict[str, LabFeeCandidateT] = {}
    for registration in registrations:
        curriculum_course = registration.section.curriculum_course
        course = curriculum_course.course
        breakdown = course_fee_breakdown(curriculum_course, registration.section.semester)
        if breakdown["credit_hours"] != 4:
            continue
        if is_general_science_course(course):
            continue
        if breakdown["extra_amount"] > Decimal("0.00"):
            continue
        key = breakdown["course_key"]
        row = grouped.get(key)
        if row is None:
            row = {
                "course_key": key,
                "course_code": course.short_code or course.code or key,
                "course_title": course.title or "",
                "credit_hours": str(breakdown["credit_hours"]),
                "computed_amount": f"{breakdown['total_amount']:.2f}",
                "registration_count": "0",
                "reason": "non-general 4-credit course has no extra_amount override",
            }
            grouped[key] = row
        row["registration_count"] = str(int(row["registration_count"]) + 1)
    return [grouped[key] for key in sorted(grouped)]


def course_key_for_course(course: "Course") -> str:
    """Return the normalized policy key for a course model."""
    return course_key(
        getattr(course.department, "code", ""), getattr(course, "number", "")
    )


@lru_cache(maxsize=1)
def load_course_fee_overrides(
    path: Path = DEFAULT_COURSE_FEE_OVERRIDES_PATH,
) -> CourseFeeOverrideMapT:
    """Load course fee overrides from the editable TSV table."""
    overrides: CourseFeeOverrideMapT = {}
    for row in _read_tsv(path):
        key = course_key(row.get("course_dept", ""), row.get("course_no", ""))
        if not key:
            continue
        overrides[key] = CourseFeeOverrideT(
            course_key=key,
            base_amount=_optional_money(row.get("base_amount", "")),
            extra_amount=_optional_money(row.get("extra_amount", "")) or Decimal("0.00"),
            fee_type_code=(row.get("fee_type_code", "") or "other").strip(),
            reason=(row.get("reason", "") or "").strip(),
        )
    return overrides


@lru_cache(maxsize=1)
def load_tuition_rates(path: Path = DEFAULT_TUITION_RATES_PATH) -> TuitionRateMapT:
    """Load semester tuition rates exported from SmartSchool."""
    rates: TuitionRateMapT = {}
    for row in _read_tsv(path):
        academic_year = normalize_academic_year(row.get("academic_year", ""))
        semester_number = _int_or_zero(row.get("semester_no", ""))
        rate = _optional_money(row.get("tuition_per_credit", ""))
        if academic_year and semester_number and rate is not None:
            rates[(academic_year, semester_number)] = rate
    return rates


def _credit_hours(curriculum_course: "CurriCrs") -> int:
    """Return credit hours as an integer, falling back to zero."""
    credit_hours = getattr(curriculum_course, "credit_hours", None)
    return _int_or_zero(str(getattr(credit_hours, "code", "") or ""))


def _read_tsv(path: Path) -> list[dict[str, str]]:
    """Read a TSV file, returning no rows when the table is absent."""
    if not path.exists():
        return []
    with path.open("r", encoding="utf-8", newline="") as handle:
        reader = csv.DictReader(handle, delimiter="\t")
        return [dict(row) for row in reader]


def _optional_money(value: str) -> MoneyT | None:
    """Return a normalized decimal amount or None for blank/invalid input."""
    raw = (value or "").strip()
    if not raw:
        return None
    try:
        return _money(Decimal(raw))
    except InvalidOperation:
        return None


def _money(value: MoneyT) -> MoneyT:
    """Normalize a decimal amount to two places."""
    return value.quantize(Decimal("0.01"), rounding=ROUND_HALF_UP)


def _int_or_zero(value: str) -> int:
    """Parse an integer-like string, returning zero on blank/invalid values."""
    try:
        return int(Decimal((value or "").strip()))
    except (InvalidOperation, ValueError):
        return 0


__all__ = [
    "CourseFeeBreakdownT",
    "CourseFeeOverrideT",
    "LabFeeCandidateT",
    "MIN_COURSE_AMOUNT",
    "course_fee_breakdown",
    "course_fee_override_for",
    "course_key_for_course",
    "course_policy_extra_amount",
    "course_tuition_amount",
    "is_general_science_course",
    "load_course_fee_overrides",
    "load_tuition_rates",
    "tuition_rate_for_semester",
    "unresolved_lab_fee_candidate_rows",
]
