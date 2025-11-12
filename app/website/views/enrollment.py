"""Enrollment officer views for student CRUD."""

from __future__ import annotations

from django.contrib import messages
from typing import cast

from django.contrib.auth.decorators import permission_required
from django.contrib.auth.models import User
from django.core.exceptions import PermissionDenied
from django.db.models import Q
from django.http import HttpRequest, HttpResponse
from django.shortcuts import get_object_or_404, redirect, render

from app.people.forms.person import StudentForm
from app.people.models.student import Student


@permission_required("people.add_student", raise_exception=True)
def create_student(request: HttpRequest) -> HttpResponse:
    """Allow enrollment officers to create a new student profile."""
    if request.method == "POST":
        form = StudentForm(request.POST)
        if form.is_valid():
            form.save()
            messages.success(request, "Student created successfully.")
            return redirect("create_student")
    else:
        form = StudentForm()

    return render(request, "website/create_student.html", {"form": form})


@permission_required("people.view_student", raise_exception=True)
def student_list(request: HttpRequest) -> HttpResponse:
    """Render a searchable list of students."""
    query = request.GET.get("q", "")
    students = Student.objects.all()
    if query:
        predicates = Q(student_id__icontains=query) | Q(username__icontains=query)
        predicates |= Q(user__first_name__icontains=query)
        predicates |= Q(user__last_name__icontains=query)
        students = students.filter(predicates)
    context = {"students": students.order_by("student_id"), "query": query}
    return render(request, "enrollment/student_list.html", context)


@permission_required("people.view_student", raise_exception=True)
def student_detail(request: HttpRequest, pk: int) -> HttpResponse:
    """Render a student profile page."""
    student = get_object_or_404(Student, pk=pk)
    return render(
        request,
        "enrollment/student_detail.html",
        {"student": student},
    )


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
        return redirect("landing")

    return render(
        request,
        "enrollment/student_confirm_delete.html",
        {"student": student},
    )
