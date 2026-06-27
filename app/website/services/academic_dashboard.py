"""Academic leader dashboard context builders for dean and chair workspaces."""

from __future__ import annotations

from typing import TypedDict

from django.db.models import QuerySet
from django.http import HttpRequest
from django.urls import reverse

from app.academics.models.college import College
from app.academics.models.curriculum import Curriculum
from app.people.models.faculty import Faculty
from app.people.models.role_assignment import RoleAssignment
from app.shared.auth.perms import UserRole
from app.timetable.models.academic_year import AcademicYear
from app.timetable.models.semester import Semester
from app.website.services.academic_dashboard_metrics import (
    DashboardContextT,
    academic_chart_context,
)


class ScopeT(TypedDict):
    """Resolved academic responsibility scope for one dashboard."""

    curricula: QuerySet[Curriculum]
    label: str


def _semester_label(semester: Semester) -> str:
    """Return a readable dashboard semester label."""
    return f"{semester.academic_year.code} · Semester {semester.number}"


def _reasonable_semester_queryset() -> QuerySet[Semester]:
    """Return semesters that should appear in current dashboard controls."""
    current_year = AcademicYear.get_dft()
    return Semester.objects.select_related("academic_year").filter(
        academic_year__start_date__lte=current_year.start_date
    )


def _dashboard_semester_queryset() -> QuerySet[Semester]:
    """Return valid dashboard terms, including terms with no scoped sections."""
    return _reasonable_semester_queryset().order_by("-start_date", "-id")


def _semester_options(selected_semester: Semester) -> list[dict[str, object]]:
    """Return valid semester options for dashboard selectors."""
    semesters = list(_dashboard_semester_queryset()[:12])
    selected_ids = {semester.id for semester in semesters}
    if selected_semester.id not in selected_ids:
        semesters.append(selected_semester)
    semesters.sort(
        key=lambda semester: (
            semester.start_date or semester.academic_year.start_date,
            semester.id,
        ),
        reverse=True,
    )
    return [
        {
            "id": semester.id,
            "label": _semester_label(semester),
            "selected": semester.id == selected_semester.id,
        }
        for semester in semesters
    ]


def selected_dashboard_semester(request: HttpRequest) -> Semester:
    """Return the requested dashboard semester, defaulting to current or latest."""
    dashboard_semesters = _dashboard_semester_queryset()
    raw_value = request.GET.get("semester")
    if raw_value:
        try:
            semester_id = int(raw_value)
        except ValueError:
            semester_id = 0
        if semester_id:
            semester = dashboard_semesters.filter(pk=semester_id).first()
            if semester is not None:
                return semester
    current_semester = Semester.get_current_sem()
    if dashboard_semesters.filter(pk=current_semester.pk).exists():
        return current_semester
    return dashboard_semesters.first() or current_semester


def _official_curricula(curricula: QuerySet[Curriculum]) -> QuerySet[Curriculum]:
    """Return curricula suitable for dashboard program statistics."""
    return curricula.filter(status_id="approved", is_active=True)


def _chair_scope_from_faculty(faculty: Faculty) -> ScopeT:
    """Resolve curricula for a chair from role assignment, then profile fallback."""
    assignments = RoleAssignment.objects.filter(
        user=faculty.staff_profile.user,
        group__name=UserRole.CHAIR.value.label,
        end_date__isnull=True,
    ).select_related("college", "department")
    department_ids = [row.department_id for row in assignments if row.department_id]
    college_ids = [row.college_id for row in assignments if row.college_id]
    if department_ids:
        return {
            "curricula": _official_curricula(
                Curriculum.objects.filter(
                    programs__course__department_id__in=department_ids
                )
            ).distinct(),
            "label": "Assigned departments",
        }
    if college_ids:
        return {
            "curricula": _official_curricula(
                Curriculum.objects.filter(college_id__in=college_ids)
            ),
            "label": "Assigned colleges",
        }
    if faculty.staff_profile.department_id:
        return {
            "curricula": _official_curricula(
                Curriculum.objects.filter(
                    programs__course__department=faculty.staff_profile.department
                )
            ).distinct(),
            "label": str(faculty.staff_profile.department),
        }
    return {
        "curricula": _official_curricula(
            Curriculum.objects.filter(college=faculty.college)
        ),
        "label": str(faculty.college),
    }


def chair_curriculum_scope(faculty: Faculty) -> ScopeT:
    """Return the curriculum scope attached to a chair profile."""
    return _chair_scope_from_faculty(faculty)


def _chair_options(
    college: College, selected_chair_id: int | None
) -> list[dict[str, object]]:
    """Return chair selector options for one dean college."""
    chairs = (
        Faculty.objects.filter(
            college=college,
            staff_profile__user__groups__name=UserRole.CHAIR.value.label,
        )
        .select_related("staff_profile__department", "staff_profile__user")
        .order_by("staff_profile__department__code", "staff_profile__user__last_name")
    )
    return [
        {
            "id": chair.id,
            "label": chair.staff_profile.long_name,
            "selected": chair.id == selected_chair_id,
        }
        for chair in chairs
    ]


def _selected_chair(request: HttpRequest, college: College) -> Faculty | None:
    """Return the selected chair in the dean's college."""
    raw_value = request.GET.get("chair_id")
    if not raw_value:
        return None
    try:
        chair_id = int(raw_value)
    except ValueError:
        return None
    return (
        Faculty.objects.filter(
            pk=chair_id,
            college=college,
            staff_profile__user__groups__name=UserRole.CHAIR.value.label,
        )
        .select_related("staff_profile__department", "staff_profile__user")
        .first()
    )


def build_dean_academic_dashboard(
    request: HttpRequest,
    *,
    college: College,
) -> DashboardContextT:
    """Return dean academic dashboard context for one college."""
    curricula = _official_curricula(Curriculum.objects.filter(college=college))
    semester = selected_dashboard_semester(request)
    selected_chair = _selected_chair(request, college)
    selected_chair_id = selected_chair.id if selected_chair else None
    context = academic_chart_context(
        title="Student enrollment by program",
        scope_label=str(college),
        curricula=curricula,
        semester=semester,
    )
    context.update(
        {
            "selected_semester": semester,
            "selected_semester_label": _semester_label(semester),
            "semester_options": _semester_options(semester),
            "chair_options": _chair_options(college, selected_chair_id),
            "dashboard_url": reverse("staff_role_dashboard", args=["dean"]),
        }
    )
    if selected_chair is not None:
        chair_scope = _chair_scope_from_faculty(selected_chair)
        context["focus"] = academic_chart_context(
            title=f"{selected_chair.staff_profile.long_name}",
            scope_label=chair_scope["label"],
            curricula=chair_scope["curricula"],
            semester=semester,
        )
    return context


def build_chair_academic_dashboard(
    request: HttpRequest,
    *,
    faculty: Faculty,
) -> DashboardContextT:
    """Return chair academic dashboard context for one chair profile."""
    scope = _chair_scope_from_faculty(faculty)
    semester = selected_dashboard_semester(request)
    context = academic_chart_context(
        title="Student enrollment by program",
        scope_label=scope["label"],
        curricula=scope["curricula"],
        semester=semester,
    )
    context.update(
        {
            "selected_semester": semester,
            "selected_semester_label": _semester_label(semester),
            "semester_options": _semester_options(semester),
            "dashboard_url": reverse("staff_role_dashboard", args=["chair"]),
        }
    )
    return context


__all__ = [
    "build_chair_academic_dashboard",
    "build_dean_academic_dashboard",
    "chair_curriculum_scope",
    "selected_dashboard_semester",
]
