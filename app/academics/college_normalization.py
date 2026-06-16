"""College-code normalization helpers for imports and DB initialization."""

from __future__ import annotations

from dataclasses import dataclass
from typing import TypeAlias, cast

from django.db import transaction
from django.db.models.fields.reverse_related import ForeignObjectRel

from app.academics.choices import COLLEGE_CODE_RENAMES, COLLEGE_LONG_NAME
from app.academics.models.college import College
from app.academics.models.curriculum import Curriculum
from app.academics.models.department import Department
from app.academics.models.course import Course

CollegeLongNameMapT: TypeAlias = dict[str, str]
CurriculumRenameMapT: TypeAlias = dict[str, str]

CANONICAL_COLLEGE_LONG_NAMES: CollegeLongNameMapT = {
    "CAS": COLLEGE_LONG_NAME["cas"],
    "CBA": COLLEGE_LONG_NAME["cba"],
    "EDRCE": COLLEGE_LONG_NAME["edrce"],
    "CET": COLLEGE_LONG_NAME["cet"],
    "CHS": COLLEGE_LONG_NAME["chs"],
    "CAFS": COLLEGE_LONG_NAME["cafs"],
    "DEFT": COLLEGE_LONG_NAME["deft"],
    "TEST": COLLEGE_LONG_NAME["test"],
}

GENERIC_CURRICULUM_RENAMES: CurriculumRenameMapT = {
    "COAS - GEN": "CAS - GEN",
    "COBA - GEN": "CBA - GEN",
    "COED - GEN": "EDRCE - GEN",
    "CED - GEN": "EDRCE - GEN",
    "COET - GEN": "CET - GEN",
    "COHS - GEN": "CHS - GEN",
}

CURRICULUM_PREFIX_RENAMES: CurriculumRenameMapT = {
    "COAS": "CAS",
    "COBA": "CBA",
    "COED": "EDRCE",
    "CED": "EDRCE",
    "COET": "CET",
    "COHS": "CHS",
}


@dataclass(frozen=True)
class CollegeNormalizationResult:
    """Summary of canonical college and generic curriculum normalization."""

    created: int = 0
    renamed: int = 0
    merged: int = 0
    related_updates: int = 0
    curriculum_updates: int = 0
    derived_code_updates: int = 0


def normalize_college_records() -> CollegeNormalizationResult:
    """Normalize saved college rows and generic curriculum labels."""
    created = renamed = merged = related_updates = curriculum_updates = 0
    derived_code_updates = 0
    with transaction.atomic():
        for old_code, new_code in COLLEGE_CODE_RENAMES.items():
            source = College.objects.filter(code=old_code).first()
            if source is None:
                continue
            canonical_long_name = CANONICAL_COLLEGE_LONG_NAMES[new_code]
            target = _canonical_target(source, new_code, canonical_long_name)
            if target is not None:
                if target.code != new_code or target.long_name != canonical_long_name:
                    target.code = new_code
                    target.long_name = canonical_long_name
                    target.save(update_fields=["code", "long_name"])
                related_updates += _move_college_relations(source, target)
                source.delete()
                merged += 1
                continue
            source.code = new_code
            source.long_name = canonical_long_name
            source.save(update_fields=["code", "long_name"])
            renamed += 1

        for code, long_name in CANONICAL_COLLEGE_LONG_NAMES.items():
            college = College.objects.filter(code=code).first()
            if college is None:
                same_name = College.objects.filter(long_name=long_name).first()
                if same_name is not None:
                    same_name.code = code
                    same_name.save(update_fields=["code"])
                    renamed += 1
                    continue
                College.objects.create(code=code, long_name=long_name)
                created += 1
                continue
            if college.long_name != long_name:
                college.long_name = long_name
                college.save(update_fields=["long_name"])
                renamed += 1

        curriculum_updates += _refresh_curriculum_short_names()
        derived_code_updates = _refresh_derived_academic_codes()

    return CollegeNormalizationResult(
        created=created,
        renamed=renamed,
        merged=merged,
        related_updates=related_updates,
        curriculum_updates=curriculum_updates,
        derived_code_updates=derived_code_updates,
    )


def _move_college_relations(source: College, target: College) -> int:
    """Repoint reverse foreign keys from a legacy college to a canonical row."""
    updated = 0
    relations = cast(
        tuple[ForeignObjectRel, ...], getattr(College._meta, "related_objects", ())
    )
    for relation in relations:
        if relation.many_to_many:
            continue
        field_name = relation.field.name
        related_model = relation.related_model
        if isinstance(related_model, str):
            continue
        manager = related_model._default_manager
        updated += manager.filter(**{field_name: source}).update(**{field_name: target})
    return updated


def _canonical_target(
    source: College, canonical_code: str, canonical_long_name: str
) -> College | None:
    """Find an existing canonical row to merge into, excluding the source row."""
    return (
        College.objects.filter(code=canonical_code).exclude(pk=source.pk).first()
        or College.objects.filter(long_name=canonical_long_name)
        .exclude(pk=source.pk)
        .first()
    )


def _refresh_derived_academic_codes() -> int:
    """Refresh department shortnames and course codes derived from college codes."""
    updated = 0
    for department in Department.objects.select_related("college"):
        expected_shortname = f"{department.college.code}_{department.code}"
        if department.shortname != expected_shortname:
            department.shortname = expected_shortname
            department.save(update_fields=["shortname"])
            updated += 1
    for course in Course.objects.select_related("department"):
        expected_code = f"{course.department.shortname}{course.number}".upper()
        if course.code != expected_code:
            course.code = expected_code
            course.save(update_fields=["code"])
            updated += 1
    return updated


def _refresh_curriculum_short_names() -> int:
    """Refresh curriculum short names that embed legacy college prefixes."""
    updated = 0
    for old_short_name, new_short_name in GENERIC_CURRICULUM_RENAMES.items():
        for curriculum in Curriculum.objects.filter(short_name=old_short_name):
            _rename_curriculum(curriculum, new_short_name)
            updated += 1
    for old_prefix, new_prefix in CURRICULUM_PREFIX_RENAMES.items():
        for curriculum in Curriculum.objects.filter(
            short_name__startswith=f"{old_prefix}-"
        ):
            new_short_name = f"{new_prefix}{curriculum.short_name[len(old_prefix) :]}"
            _rename_curriculum(curriculum, new_short_name)
            updated += 1
    return updated


def _rename_curriculum(curriculum: Curriculum, new_short_name: str) -> None:
    """Rename one curriculum and keep its derived code in sync."""
    curriculum.short_name = new_short_name
    curriculum.code = (
        f"({curriculum.college.code}) {new_short_name}"
        if curriculum.college_id
        else new_short_name
    )
    curriculum.save(update_fields=["short_name", "code"])


__all__ = [
    "CollegeNormalizationResult",
    "GENERIC_CURRICULUM_RENAMES",
    "normalize_college_records",
]
