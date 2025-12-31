"""Utilities to merge duplicate person records safely."""

from __future__ import annotations

import logging
from typing import Iterable, TypeVar

from django.contrib.auth.models import User
from django.db import transaction

from app.people.models.faculty import Faculty
from app.people.models.role_assignment import RoleAssignment
from app.people.models.staffs import Staff
from app.people.models.student import Student
from app.people.models.donor import Donor
from app.timetable.models.section import Section

logger = logging.getLogger(__name__)

PersonType = TypeVar("PersonType", Staff, Student)


def _merge_users(target_user: User, source_user: User) -> None:
    """Merge groups/roles from source_user into target_user."""
    for group in source_user.groups.all():
        target_user.groups.add(group)
    for perm in source_user.user_permissions.all():
        target_user.user_permissions.add(perm)
    RoleAssignment.objects.filter(user=source_user).update(user=target_user)
    target_user.is_staff = target_user.is_staff or source_user.is_staff
    target_user.is_superuser = target_user.is_superuser or source_user.is_superuser
    target_user.save()


@transaction.atomic
def merge_users(target_user: User, source_user: User) -> User:
    """Merge auth users and any attached person profiles."""
    if target_user.pk == source_user.pk:
        return target_user

    if not target_user.pk:
        raise ValueError("Target user must be saved before merging.")
    if not source_user.pk:
        # Nothing to merge if source isn't saved
        return target_user

    # Merge linked profiles
    for attr in ("staff", "student", "donor"):
        target_profile = getattr(target_user, attr, None)
        source_profile = getattr(source_user, attr, None)
        if target_profile and source_profile:
            merge_people(target_profile, source_profile)
        elif source_profile and not target_profile:
            source_profile.user = target_user
            source_profile.save()

    _merge_users(target_user, source_user)
    source_user.delete()
    return target_user


def _copy_if_missing(target, source, fields: Iterable[str]) -> None:
    """Copy non-empty source values into empty target fields."""
    for field in fields:
        if not hasattr(target, field) or not hasattr(source, field):
            continue
        target_val = getattr(target, field, None)
        source_val = getattr(source, field, None)
        if (not target_val) and source_val:
            setattr(target, field, source_val)
        elif isinstance(source_val, str) and isinstance(target_val, str):
            if len(source_val) > len(target_val):
                setattr(target, field, source_val)


@transaction.atomic
def merge_people(target: PersonType, source: PersonType) -> PersonType:
    """Merge a source person into target, reassigning relations and deleting source."""
    if target.pk == source.pk:
        return target
    if type(target) is not type(source):
        raise ValueError("Can only merge people of the same model.")

    _merge_users(target.user, source.user)

    # Copy basic profile info where missing
    base_fields = [
        "bio",
        "phone_number",
        "physical_address",
        "birth_date",
        "gender",
        "nationality",
        "origin_county",
        "marital_status",
        "father_name",
        "father_address",
        "photo",
    ]
    _copy_if_missing(target, source, base_fields)

    if isinstance(target, Staff):
        staff_fields = ["division", "department", "employment_date", "position"]
        _copy_if_missing(target, source, staff_fields)

        source_faculty = Faculty.objects.filter(staff_profile=source).first()
        target_faculty = Faculty.objects.filter(staff_profile=target).first()

        if source_faculty and target_faculty:
            Section.objects.filter(faculty=source_faculty).update(faculty=target_faculty)
            source_faculty.delete()
        elif source_faculty and not target_faculty:
            source_faculty.staff_profile = target
            source_faculty.save()

    if isinstance(target, Student):
        student_fields = [
            "curriculum",
            "entry_semester",
            "current_enrolled_semester",
            "birth_place",
        ]
        _copy_if_missing(target, source, student_fields)
        target.middle_name = target.middle_name or source.middle_name
        target.name_prefix = target.name_prefix or source.name_prefix
        target.name_suffix = target.name_suffix or source.name_suffix

    # Append a merge note in bio to keep traceability
    merge_note = f"[merged from {source.pk}/{getattr(source, 'obj_id', '')}]"
    if merge_note not in (target.bio or ""):
        target.bio = (
            (target.bio or "").rstrip() + (" " if target.bio else "") + merge_note
        )

    target.save()

    # Once relations are repointed, remove source user if unused
    src_user = source.user
    source.delete()
    if src_user != target.user:
        still_used = (
            Staff.objects.filter(user=src_user).exists()
            or Student.objects.filter(user=src_user).exists()
            or Donor.objects.filter(user=src_user).exists()
        )
        if not still_used:
            try:
                src_user.delete()
            except Exception:
                logger.warning("Could not delete merged user", exc_info=True)

    return target
