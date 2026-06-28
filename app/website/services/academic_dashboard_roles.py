"""Role-assignment helpers for academic dashboard scopes."""

from __future__ import annotations

from dataclasses import dataclass
from typing import cast

from django.contrib.auth.models import User
from django.db.models import QuerySet

from app.academics.models.college import College
from app.people.models.faculty import Faculty
from app.people.models.role_assignment import RoleAssignment
from app.shared.auth.perms import UserRole


@dataclass(frozen=True)
class DeanScope:
    """Concrete dean dashboard scope exposed to VPAA selectors."""

    id: str
    label: str
    college: College
    user: User


def active_dean_role_assignments() -> QuerySet[RoleAssignment]:
    """Return active dean roles that are attached to one college."""
    return (
        RoleAssignment.objects.filter(
            group__name=UserRole.DEAN.value.label,
            end_date__isnull=True,
            college__isnull=False,
        )
        .select_related("college", "user")
        .order_by("college__code", "-start_date", "-id")
    )


def _user_label(user: User) -> str:
    """Return a readable name for selector labels."""
    full_name = user.get_full_name().strip()
    return full_name or user.username


def _role_scope(role: RoleAssignment) -> DeanScope | None:
    """Return a selector scope for one explicit dean role."""
    college = role.college
    if college is None:
        return None
    return DeanScope(
        id=str(role.id),
        label=f"{college.code} - {_user_label(role.user)}",
        college=college,
        user=role.user,
    )


def _faculty_scope(faculty: Faculty) -> DeanScope | None:
    """Return a selector scope from dean group membership and faculty college."""
    college = faculty.college
    if college is None:
        return None
    user = faculty.staff_profile.user
    return DeanScope(
        id=f"faculty:{faculty.id}",
        label=f"{college.code} - {_user_label(user)}",
        college=college,
        user=user,
    )


def dean_scopes() -> list[DeanScope]:
    """Return VPAA-visible dean scopes from roles and profile fallbacks."""
    scopes: list[DeanScope] = []
    seen: set[tuple[int, int]] = set()
    seen_colleges: set[int] = set()
    for role in active_dean_role_assignments():
        scope = _role_scope(role)
        if scope is None:
            continue
        if scope.college.id in seen_colleges:
            continue
        scopes.append(scope)
        seen.add((scope.user.id, scope.college.id))
        seen_colleges.add(scope.college.id)

    faculty_rows = (
        Faculty.objects.filter(
            staff_profile__user__groups__name=UserRole.DEAN.value.label,
            college__isnull=False,
        )
        .select_related("college", "staff_profile__user")
        .order_by(
            "college__code",
            "staff_profile__user__last_name",
            "staff_profile__user__first_name",
            "id",
        )
    )
    for faculty in faculty_rows:
        scope = _faculty_scope(faculty)
        if scope is None:
            continue
        key = (scope.user.id, scope.college.id)
        if key in seen or scope.college.id in seen_colleges:
            continue
        scopes.append(scope)
        seen.add(key)
        seen_colleges.add(scope.college.id)
    return scopes


def dean_role_options(selected_role_id: object | None) -> list[dict[str, object]]:
    """Return VPAA dean selector options from active role scopes."""
    selected_id = str(selected_role_id or "")
    options: list[dict[str, object]] = []
    for scope in dean_scopes():
        options.append(
            {
                "id": scope.id,
                "label": scope.label,
                "selected": scope.id == selected_id,
            }
        )
    return options


def selected_dean_role(raw_value: str | None) -> DeanScope | None:
    """Return the selected active dean scope, or none for prompt state."""
    if not raw_value:
        return None
    for scope in dean_scopes():
        if scope.id == raw_value:
            return scope
    return None


def dean_college_for_user(user: User) -> College | None:
    """Return a dean's college from role assignment, then faculty fallback."""
    role = active_dean_role_assignments().filter(user=user).first()
    if role is not None and role.college is not None:
        return role.college
    staff = getattr(user, "staff", None)
    if staff is None:
        return None
    try:
        faculty = cast(Faculty, staff.faculty)
    except Faculty.DoesNotExist:
        return None
    return faculty.college


__all__ = [
    "DeanScope",
    "active_dean_role_assignments",
    "dean_college_for_user",
    "dean_role_options",
    "dean_scopes",
    "selected_dean_role",
]
