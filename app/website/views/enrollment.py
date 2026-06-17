"""Enrollment officer views for student workflows."""

from __future__ import annotations

from typing import cast

from django import forms
from django.contrib import messages
from django.contrib.auth.decorators import permission_required
from django.contrib.auth.models import User
from django.core.exceptions import PermissionDenied
from django.http import HttpRequest, HttpResponse, JsonResponse
from django.shortcuts import get_object_or_404, redirect, render
from django.urls import reverse

from app.people.models.student import Student
from app.shared.utils import parse_str
from app.website.forms.enrollment import StudentIntakeForm, save_student_intake
from app.website.services.enrollment_portal import (
    apply_student_filters,
    build_curriculum_autocomplete_results,
    build_student_autocomplete_results,
    build_student_detail_context,
    build_student_directory_context,
    enrollment_admin_shortcuts,
    student_search_queryset,
    StudentFiltersT,
)
from app.website.services.staff_portal import (
    build_staff_role_switcher,
    build_staff_sidebar_links,
)


class StdAdminLookupForm(forms.Form):
    """Small helper form that opens a student profile inside the portal."""

    student = forms.IntegerField(widget=forms.HiddenInput(), required=False)
    student_query = forms.CharField(
        label="Student ID, name, college, program, or semester",
        widget=forms.TextInput(
            attrs={
                "class": "form-control",
                "placeholder": "Start typing a student ID, name, program, or college...",
                "autocomplete": "off",
            }
        ),
    )

    def clean(self) -> dict[str, object]:
        """Resolve a selected or exact-match student from the lookup field."""
        cleaned = dict(super().clean() or {})
        if cleaned.get("student"):
            return cleaned
        query = parse_str(cleaned.get("student_query"))
        if not query:
            raise forms.ValidationError("Select a student from the search results.")

        filters: StudentFiltersT = {
            "q": query,
            "college": None,
            "program": None,
            "semester": None,
        }
        student = apply_student_filters(student_search_queryset(), filters).first()
        if not student:
            raise forms.ValidationError("Select a student from the autocomplete list.")
        cleaned["student"] = student.pk
        return cleaned


def _enrollment_user(request: HttpRequest) -> User:
    """Return request.user as a concrete auth user for enrollment context."""
    return cast(User, request.user)


def _enrollment_role_slug(user: User) -> str:
    """Return the active enrollment role slug for sidebar and switcher state."""
    if user.groups.filter(name="Enrollment Officer").exists():
        return "enrollment_officer"
    return "enrollment"


def _staff_breadcrumb(label: str, user: User) -> list[dict[str, str]]:
    """Return enrollment breadcrumbs for staff portal pages."""
    role_slug = _enrollment_role_slug(user)
    role_label = (
        "Enrollment officer desk"
        if role_slug == "enrollment_officer"
        else "Enrollment desk"
    )
    return [
        {
            "label": role_label,
            "href": reverse("staff_role_dashboard", args=[role_slug]),
        },
        {"label": label, "href": ""},
    ]


def _shell_context(
    request: HttpRequest,
    *,
    active_key: str,
    label: str,
) -> dict[str, object]:
    """Return common enrollment portal shell values."""
    user = _enrollment_user(request)
    role_slug = _enrollment_role_slug(user)
    return {
        "sidebar_links": build_staff_sidebar_links(role_slug, active_key),
        "role_switcher": build_staff_role_switcher(user, role_slug),
        "breadcrumbs": _staff_breadcrumb(label, user),
        "admin_shortcuts": enrollment_admin_shortcuts(user),
    }


def _selected_student(request: HttpRequest) -> Student | None:
    """Return the student selected for portal editing, when present."""
    raw_student_id = request.GET.get("student_id") or request.POST.get("student_id")
    student_id = parse_str(raw_student_id)
    if not student_id:
        return None
    return (
        Student.objects.select_related("user")
        .filter(student_id__iexact=student_id)
        .first()
    )


@permission_required("people.add_student", raise_exception=True)
def create_std(request: HttpRequest) -> HttpResponse:
    """Create or update a student profile from the portal."""
    student = _selected_student(request)
    form = StudentIntakeForm(
        request.POST or None,
        student=student,
    )
    if request.method == "POST" and form.is_valid():
        student = save_student_intake(form, student)
        messages.success(request, f"{student.long_name} is ready in Tusis.")
        return redirect("std_detail", pk=student.pk)

    mode_label = "Update student" if student else "Create student"
    context: dict[str, object] = {
        "form": form,
        "student": student,
        "page_title": mode_label,
        "page_summary": "Capture the full enrollment record without leaving the Tusis portal.",
        "eyebrow": "Enrollment",
        "curriculum_autocomplete_url": reverse("curriculum_autocomplete"),
    }
    context.update(_shell_context(request, active_key="create_student", label=mode_label))
    return render(request, "website/create_student.html", context)


@permission_required("people.view_student", raise_exception=True)
def std_list(request: HttpRequest) -> HttpResponse:
    """Render a filterable student directory for enrollment staff."""
    context: dict[str, object] = {
        **build_student_directory_context(request),
        "page_title": "Student directory",
        "page_summary": "Find, review, and update student records by ID, name, college, program, or semester.",
        "eyebrow": "Enrollment",
    }
    context.update(
        _shell_context(request, active_key="student_directory", label="Student directory")
    )
    return render(request, "enrollment/student_list.html", context)


@permission_required("people.view_student", raise_exception=True)
def std_detail(request: HttpRequest, pk: int) -> HttpResponse:
    """Render a grouped student profile review page."""
    user = _enrollment_user(request)
    student = get_object_or_404(Student.objects.select_related("user"), pk=pk)
    context: dict[str, object] = {
        **build_student_detail_context(student, user),
        "student": student,
        "page_title": student.long_name,
        "page_summary": f"Student ID {student.student_id}",
        "eyebrow": "Enrollment",
    }
    context.update(
        _shell_context(request, active_key="student_directory", label=student.long_name)
    )
    return render(request, "enrollment/student_detail.html", context)


@permission_required("people.delete_student", raise_exception=True)
def std_delete(request: HttpRequest, pk: int) -> HttpResponse:
    """Delete a student after confirmation."""
    user = _enrollment_user(request)
    if not user.groups.filter(name="Enrollment Officer").exists():
        raise PermissionDenied("Only officers may delete students.")

    student = get_object_or_404(Student, pk=pk)
    if request.method == "POST":
        student.delete()
        messages.success(request, "Student deleted successfully.")
        return redirect("std_list")

    context: dict[str, object] = {
        "student": student,
        "page_title": f"Delete {student.long_name}",
        "page_summary": "Once deleted, this record cannot be recovered.",
        "eyebrow": "Enrollment",
    }
    context.update(
        _shell_context(request, active_key="student_directory", label="Delete student")
    )
    return render(request, "enrollment/student_confirm_delete.html", context)


@permission_required("people.view_student", raise_exception=True)
def std_admin_edit(request: HttpRequest) -> HttpResponse:
    """Provide a simple selector that opens a portal student profile."""
    form = StdAdminLookupForm(request.POST or None)
    if request.method == "POST" and form.is_valid():
        student_pk = form.cleaned_data["student"]
        student = get_object_or_404(Student, pk=student_pk)
        return redirect("std_detail", pk=student.pk)

    context: dict[str, object] = {
        **build_student_directory_context(request),
        "form": form,
        "page_title": "Find student",
        "page_summary": "Search by ID, name, college, program, or semester and open the portal profile.",
        "eyebrow": "Enrollment",
        "autocomplete_url": reverse("std_autocomplete"),
    }
    context.update(
        _shell_context(request, active_key="student_lookup", label="Find student")
    )
    return render(request, "enrollment/student_admin_edit.html", context)


@permission_required("people.view_student", raise_exception=True)
def std_autocomplete(request: HttpRequest) -> HttpResponse:
    """Provide JSON suggestions for the student lookup."""
    return JsonResponse({"results": build_student_autocomplete_results(request)})


@permission_required("people.view_student", raise_exception=True)
def curriculum_autocomplete(request: HttpRequest) -> HttpResponse:
    """Provide JSON suggestions for the program/curriculum selector."""
    return JsonResponse({"results": build_curriculum_autocomplete_results(request)})
