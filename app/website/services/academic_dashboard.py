"""Academic leader dashboard context builders for dean and chair workspaces."""

from __future__ import annotations

from typing import TypedDict

from django.db.models import Q, QuerySet
from django.http import HttpRequest
from django.urls import reverse

from app.academics.career_scope import (
    CareerModeT,
    academic_career_label,
    career_filter_options,
    filter_by_academic_career,
    selected_academic_career,
)
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
from app.website.services.academic_dashboard_roles import (
    dean_role_options,
    selected_dean_role,
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


def _college_label(college: College) -> str:
    """Return a readable college label for dashboard headings."""
    return college.long_name or college.code


def _dashboard_controls(
    semester: Semester,
    *,
    role: str,
    career: CareerModeT,
) -> dict[str, object]:
    """Return common form controls for academic dashboards."""
    return {
        "selected_semester": semester,
        "selected_semester_label": _semester_label(semester),
        "semester_options": _semester_options(semester),
        "selected_academic_career": career,
        "selected_academic_career_label": academic_career_label(career),
        "career_options": career_filter_options(career),
        "dashboard_url": reverse("staff_role_dashboard", args=[role]),
    }


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
    if faculty.college_id is None or faculty.college is None:
        return {
            "curricula": Curriculum.objects.none(),
            "label": "Unassigned college",
        }
    college = faculty.college
    return {
        "curricula": _official_curricula(Curriculum.objects.filter(college=college)),
        "label": _college_label(college),
    }


def chair_curriculum_scope(faculty: Faculty) -> ScopeT:
    """Return the curriculum scope attached to a chair profile."""
    return _chair_scope_from_faculty(faculty)


def _chair_options(
    college: College, selected_chair_id: int | None
) -> list[dict[str, object]]:
    """Return chair selector options for one dean college."""
    chairs = _chair_faculty_queryset(college).order_by(
        "staff_profile__department__code",
        "staff_profile__user__last_name",
        "staff_profile__user__first_name",
        "id",
    )
    return [
        {
            "id": chair.id,
            "label": chair.staff_profile.long_name,
            "selected": chair.id == selected_chair_id,
        }
        for chair in chairs
    ]


def _chair_faculty_queryset(college: College) -> QuerySet[Faculty]:
    """Return chair faculty rows attached to one dean college."""
    return (
        Faculty.objects.filter(
            staff_profile__user__groups__name=UserRole.CHAIR.value.label
        )
        .filter(
            Q(college=college)
            | Q(staff_profile__department__college=college)
            | Q(
                staff_profile__user__role_assignments__group__name=UserRole.CHAIR.value.label,
                staff_profile__user__role_assignments__college=college,
                staff_profile__user__role_assignments__end_date__isnull=True,
            )
            | Q(
                staff_profile__user__role_assignments__group__name=UserRole.CHAIR.value.label,
                staff_profile__user__role_assignments__department__college=college,
                staff_profile__user__role_assignments__end_date__isnull=True,
            )
        )
        .select_related("staff_profile__department", "staff_profile__user")
        .distinct()
    )


def _selected_chair(request: HttpRequest, college: College) -> Faculty | None:
    """Return the selected chair in the dean's college."""
    raw_value = request.GET.get("chair_id")
    if not raw_value:
        return None
    try:
        chair_id = int(raw_value)
    except ValueError:
        return None
    return _chair_faculty_queryset(college).filter(pk=chair_id).first()


def build_dean_academic_dashboard(
    request: HttpRequest,
    *,
    college: College,
) -> DashboardContextT:
    """Return dean academic dashboard context for one college."""
    career = selected_academic_career(request.GET)
    curricula = filter_by_academic_career(
        _official_curricula(Curriculum.objects.filter(college=college)),
        "academic_career",
        career,
    )
    semester = selected_dashboard_semester(request)
    selected_chair = _selected_chair(request, college)
    selected_chair_id = selected_chair.id if selected_chair else None
    context = academic_chart_context(
        title="Student enrollment by program",
        scope_label=_college_label(college),
        curricula=curricula,
        semester=semester,
    )
    context.update(
        {
            **_dashboard_controls(semester, role="dean", career=career),
            "chair_options": _chair_options(college, selected_chair_id),
        }
    )
    if selected_chair is not None:
        chair_scope = _chair_scope_from_faculty(selected_chair)
        chair_curricula = filter_by_academic_career(
            chair_scope["curricula"],
            "academic_career",
            career,
        )
        context["focus"] = academic_chart_context(
            title=f"{selected_chair.staff_profile.long_name}",
            scope_label=chair_scope["label"],
            curricula=chair_curricula,
            semester=semester,
        )
    return context


def build_chair_academic_dashboard(
    request: HttpRequest,
    *,
    faculty: Faculty,
) -> DashboardContextT:
    """Return chair academic dashboard context for one chair profile."""
    career = selected_academic_career(request.GET)
    scope = _chair_scope_from_faculty(faculty)
    curricula = filter_by_academic_career(
        scope["curricula"],
        "academic_career",
        career,
    )
    semester = selected_dashboard_semester(request)
    context = academic_chart_context(
        title="Student enrollment by program",
        scope_label=scope["label"],
        curricula=curricula,
        semester=semester,
    )
    context.update(_dashboard_controls(semester, role="chair", career=career))
    return context


def build_vpaa_academic_dashboard(request: HttpRequest) -> DashboardContextT:
    """Return VPAA dean-overview dashboard context for a selected dean role."""
    semester = selected_dashboard_semester(request)
    career = selected_academic_career(request.GET)
    selected_role = selected_dean_role(request.GET.get("dean_role_id"))
    selected_role_id = selected_role.id if selected_role is not None else None
    controls = _dashboard_controls(semester, role="vpaa", career=career)
    options = dean_role_options(selected_role_id)
    if selected_role is None or selected_role.college is None:
        return {
            "title": "Dean overview",
            "scope_label": "Select a dean/college",
            **controls,
            "dean_role_options": options,
            "empty_message": (
                "Select a dean or college to load enrollment, workload, and "
                "schedule data."
            ),
        }

    college = selected_role.college
    curricula = filter_by_academic_career(
        _official_curricula(Curriculum.objects.filter(college=college)),
        "academic_career",
        career,
    )
    context = academic_chart_context(
        title="Dean overview",
        scope_label=_college_label(college),
        curricula=curricula,
        semester=semester,
    )
    context.update(
        {
            **controls,
            "dean_role_options": options,
        }
    )
    return context


__all__ = [
    "build_chair_academic_dashboard",
    "build_dean_academic_dashboard",
    "build_vpaa_academic_dashboard",
    "chair_curriculum_scope",
    "selected_dashboard_semester",
]
