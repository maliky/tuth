"""Enrollment officer views for student workflows."""

from __future__ import annotations

from typing import cast

from django import forms
from django.contrib import messages
from django.contrib.auth.decorators import permission_required
from django.contrib.auth.models import User
from django.core.exceptions import PermissionDenied
from django.db.models import Q
from django.http import HttpRequest, HttpResponse, JsonResponse
from django.shortcuts import get_object_or_404, redirect, render
from django.urls import reverse

from app.people.models.student import Student
from app.shared.utils import parse_str
from app.website.forms.enrollment import StudentIntakeForm, save_student_intake
from app.website.services.staff_portal import (
    build_staff_role_switcher,
    build_staff_sidebar_links,
)


class StdAdminLookupForm(forms.Form):
    """Small helper form that opens a student profile inside the portal."""

    student = forms.IntegerField(widget=forms.HiddenInput(), required=False)
    student_query = forms.CharField(
        label="Student ID or name",
        widget=forms.TextInput(
            attrs={
                "class": "form-control",
                "placeholder": "Start typing a student ID or name...",
                "autocomplete": "off",
            }
        ),
    )

    def clean(self) -> dict[str, object]:
        cleaned = dict(super().clean() or {})
        if cleaned.get("student"):
            return cleaned
        query = parse_str(cleaned.get("student_query"))
        if not query:
            raise forms.ValidationError("Select a student from the search results.")

        student = (
            Student.objects.filter(last_enrolled_semester__isnull=False)
            .filter(Q(student_id__iexact=query) | Q(long_name__iexact=query))
            .order_by("student_id")
            .first()
        )
        if not student:
            raise forms.ValidationError("Select a student from the autocomplete list.")
        cleaned["student"] = student.pk
        return cleaned


def _staff_breadcrumb(label: str) -> list[dict[str, str]]:
    return [
        {
            "label": "Enrollment desk",
            "href": reverse("staff_role_dashboard", args=["enrollment"]),
        },
        {"label": label, "href": ""},
    ]


def _selected_student(request: HttpRequest) -> Student | None:
    """Return the student selected for portal editing, when present."""
    raw_student_id = request.POST.get("student_id") or request.GET.get("student_id")
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
    context = {
        "form": form,
        "student": student,
        "page_title": mode_label,
        "page_summary": "Capture the core admissions record without leaving the Tusis portal.",
        "eyebrow": "Enrollment",
        "sidebar_links": build_staff_sidebar_links("enrollment", "create_student"),
        "role_switcher": build_staff_role_switcher(
            cast(User, request.user), "enrollment"
        ),
        "breadcrumbs": _staff_breadcrumb(mode_label),
    }
    return render(request, "website/create_student.html", context)


@permission_required("people.view_student", raise_exception=True)
def std_list(request: HttpRequest) -> HttpResponse:
    """Render a lightweight snapshot of recent students."""
    students = Student.objects.order_by("-id")[:25]
    context = {
        "students": students,
        "page_title": "Student snapshot",
        "page_summary": "Review recent student profiles and continue enrollment work inside Tusis.",
        "eyebrow": "Enrollment",
        "sidebar_links": build_staff_sidebar_links("enrollment", "student_snapshot"),
        "role_switcher": build_staff_role_switcher(
            cast(User, request.user), "enrollment"
        ),
        "breadcrumbs": _staff_breadcrumb("Directory snapshot"),
    }
    return render(request, "enrollment/student_list.html", context)


@permission_required("people.view_student", raise_exception=True)
def std_detail(request: HttpRequest, pk: int) -> HttpResponse:
    """Render a student profile card."""
    student = get_object_or_404(Student, pk=pk)
    context = {
        "student": student,
        "page_title": student.long_name,
        "page_summary": f"Student ID {student.student_id}",
        "eyebrow": "Enrollment",
        "sidebar_links": build_staff_sidebar_links("enrollment", "student_snapshot"),
        "role_switcher": build_staff_role_switcher(
            cast(User, request.user), "enrollment"
        ),
        "breadcrumbs": _staff_breadcrumb(student.long_name),
    }
    return render(request, "enrollment/student_detail.html", context)


@permission_required("people.delete_student", raise_exception=True)
def std_delete(request: HttpRequest, pk: int) -> HttpResponse:
    """Delete a student after confirmation."""
    user = cast(User, request.user)
    if not user.groups.filter(name="Enrollment Officer").exists():
        raise PermissionDenied("Only officers may delete students.")

    student = get_object_or_404(Student, pk=pk)
    if request.method == "POST":
        student.delete()
        messages.success(request, "Student deleted successfully.")
        return redirect("std_list")

    context = {
        "student": student,
        "page_title": f"Delete {student.long_name}",
        "page_summary": "Once deleted, this record cannot be recovered.",
        "eyebrow": "Enrollment",
        "sidebar_links": build_staff_sidebar_links("enrollment", "student_snapshot"),
        "role_switcher": build_staff_role_switcher(
            cast(User, request.user), "enrollment"
        ),
        "breadcrumbs": _staff_breadcrumb("Delete student"),
    }
    return render(request, "enrollment/student_confirm_delete.html", context)


@permission_required("people.view_student", raise_exception=True)
def std_admin_edit(request: HttpRequest) -> HttpResponse:
    """Provide a simple selector that opens a portal student profile."""
    form = StdAdminLookupForm(request.POST or None)
    if request.method == "POST" and form.is_valid():
        student_pk = form.cleaned_data["student"]
        student = get_object_or_404(Student, pk=student_pk)
        return redirect("std_detail", pk=student.pk)

    context = {
        "form": form,
        "page_title": "Find student",
        "page_summary": "Pick an ID and Tusis will open the portal profile.",
        "eyebrow": "Enrollment",
        "sidebar_links": build_staff_sidebar_links("enrollment", "student_lookup"),
        "role_switcher": build_staff_role_switcher(
            cast(User, request.user), "enrollment"
        ),
        "breadcrumbs": _staff_breadcrumb("Edit student"),
        "autocomplete_url": reverse("std_autocomplete"),
    }
    return render(request, "enrollment/student_admin_edit.html", context)


@permission_required("people.view_student", raise_exception=True)
def std_autocomplete(request: HttpRequest) -> HttpResponse:
    """Provide JSON suggestions for the student lookup."""
    query = parse_str(request.GET.get("q"))
    students = Student.objects.filter(last_enrolled_semester__isnull=False)
    if query:
        students = students.filter(
            Q(student_id__icontains=query) | Q(long_name__icontains=query)
        )
    else:
        students = students.none()
    suggestions = students.order_by("student_id")[:15]
    results = [
        {
            "pk": student.pk,
            "label": f"{student.student_id} — {student.long_name}",
            "student_id": student.student_id,
            "curriculum": student.primary_curriculum.short_name,
        }
        for student in suggestions
    ]
    return JsonResponse({"results": results})
