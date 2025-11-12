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


class StudentAdminLookupForm(forms.Form):
    """Small helper form that jumps to the Django admin edit screen."""

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
        cleaned = super().clean()
        if cleaned.get("student"):
            return cleaned
        query = (cleaned.get("student_query") or "").strip()
        if not query:
            raise forms.ValidationError("Select a student from the search results.")

        student = (
            Student.objects.filter(current_enrolled_semester__isnull=False)
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


@permission_required("people.add_student", raise_exception=True)
def create_student(request: HttpRequest) -> HttpResponse:
    """Point staff to the Django admin form."""
    context = {
        "page_title": "Create student",
        "page_summary": "Use the Django admin admissions form to capture the official record.",
        "breadcrumbs": _staff_breadcrumb("Create student"),
    }
    return render(request, "website/create_student.html", context)


@permission_required("people.view_student", raise_exception=True)
def student_list(request: HttpRequest) -> HttpResponse:
    """Render a lightweight snapshot of recent students."""
    students = Student.objects.order_by("-id")[:25]
    context = {
        "students": students,
        "page_title": "Student snapshot",
        "page_summary": "This list shows the latest entries. Use Django admin for full search and filters.",
        "breadcrumbs": _staff_breadcrumb("Directory snapshot"),
    }
    return render(request, "enrollment/student_list.html", context)


@permission_required("people.view_student", raise_exception=True)
def student_detail(request: HttpRequest, pk: int) -> HttpResponse:
    """Render a student profile card."""
    student = get_object_or_404(Student, pk=pk)
    context = {
        "student": student,
        "page_title": student.long_name,
        "page_summary": f"Student ID {student.student_id}",
        "breadcrumbs": _staff_breadcrumb(student.long_name),
    }
    return render(request, "enrollment/student_detail.html", context)


@permission_required("people.delete_student", raise_exception=True)
def student_delete(request: HttpRequest, pk: int) -> HttpResponse:
    """Delete a student after confirmation."""
    user = cast(User, request.user)
    if not user.groups.filter(name="Enrollment Officer").exists():
        raise PermissionDenied("Only officers may delete students.")

    student = get_object_or_404(Student, pk=pk)
    if request.method == "POST":
        student.delete()
        messages.success(request, "Student deleted successfully.")
        return redirect("student_list")

    context = {
        "student": student,
        "page_title": f"Delete {student.long_name}",
        "page_summary": "Once deleted, this record cannot be recovered.",
        "breadcrumbs": _staff_breadcrumb("Delete student"),
    }
    return render(request, "enrollment/student_confirm_delete.html", context)


@permission_required("people.view_student", raise_exception=True)
def student_admin_edit(request: HttpRequest) -> HttpResponse:
    """Provide a simple selector that jumps to the Django admin edit form."""
    form = StudentAdminLookupForm(request.POST or None)
    if request.method == "POST" and form.is_valid():
        student_pk = form.cleaned_data["student"]
        student = get_object_or_404(Student, pk=student_pk)
        return redirect(reverse("admin:people_student_change", args=[student.pk]))

    context = {
        "form": form,
        "page_title": "Edit student in admin",
        "page_summary": "Pick an ID and Tusis will open the Django admin edit form in a new tab.",
        "breadcrumbs": _staff_breadcrumb("Edit student"),
        "autocomplete_url": reverse("student_autocomplete"),
    }
    return render(request, "enrollment/student_admin_edit.html", context)


@permission_required("people.view_student", raise_exception=True)
def student_autocomplete(request: HttpRequest) -> HttpResponse:
    """Provide JSON suggestions for the student lookup."""
    query = (request.GET.get("q") or "").strip()
    students = Student.objects.filter(current_enrolled_semester__isnull=False)
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
            "curriculum": student.curriculum.short_name if student.curriculum else "",
        }
        for student in suggestions
    ]
    return JsonResponse({"results": results})
