"""Actions module."""

# app/academics/admin/actions.py
from django import forms
from django.contrib import admin, messages
from django.contrib.admin.helpers import ACTION_CHECKBOX_NAME
from django.shortcuts import redirect, render

from app.academics.models.college import College
from app.academics.models.curriculum import Curriculum
from app.academics.models.department import Department


@admin.action(description="Bulk update departments")
def update_department(modeladmin, request, queryset):
    """Bulk-update the Department of selected courses."""

    class _DepartmentUpdateForm(forms.Form):
        """The Department for a bulk action."""

        dept = forms.ModelChoiceField(
            queryset=Department.objects.all().order_by("short_name"),
            label="Departement to be updated to",
        )
        # forms.CharField(label="New Department Code", max_length=20)

    if "apply" in request.POST:
        form = _DepartmentUpdateForm(request.POST)
        if form.is_valid():
            new_dept = form.cleaned_data["dept"]
            count = queryset.update(department=new_dept)
            modeladmin.message_user(
                request,
                f"{count} course(s) updated to {new_dept}.",
                messages.SUCCESS,
            )
            return redirect(request.get_full_path())
    else:
        form = _DepartmentUpdateForm()

    return render(
        request,
        "admin/update_department.html",
        context={
            "courses": queryset,
            "form": form,
            "title": "Confirm Department update",
            "action_checkbox_name": admin.helpers.ACTION_CHECKBOX_NAME,
        },
    )


@admin.action(description="Bulk curriculum update")
def update_curriculum(modeladmin, request, queryset):
    """Bulk-update the curriculum FK on selected prerequisites.

    Works in two steps:
      1. GET  → show a tiny form asking for the Curriculum.
      2. POST → apply it and send a flash message.
    """

    class HiddenIdListField(forms.MultipleChoiceField):
        def validate(self, value):
            pass  # allow any IDs

    class _CurriculumForm(forms.Form):
        """Capture the curriculum for the bulk action.

        The form keeps the primary keys of the selected element in
        _selected_item and exposes a curriculum field for the admin
        user to pick the destination curriculum_course.
        """

        _selected_action = HiddenIdListField(widget=forms.MultipleHiddenInput)
        curriculum = forms.ModelChoiceField(
            queryset=Curriculum.objects.all(),
            label="Curriculum to apply",
        )

    if "apply" in request.POST:
        form = _CurriculumForm(request.POST)
        if form.is_valid():
            curriculum = form.cleaned_data["curriculum"]
            # selected_ids = form.cleaned_data["_selected_action"]
            # qs = queryset.model.objects.filter(pk__in=selected_ids)
            count = queryset.update(curriculum=curriculum)
            modeladmin.message_user(
                request,
                f"{count} course(s) were linked to {curriculum}.",
                messages.SUCCESS,
            )
            return redirect(request.get_full_path())
        else:
            pass

    else:
        form = _CurriculumForm(
            initial={
                "_selected_action": request.POST.getlist(
                    admin.helpers.ACTION_CHECKBOX_NAME
                )
            }
        )

    return render(
        request,
        "admin/update_curriculum.html",
        context={"courses": queryset, "form": form, "title": "Bulk-set curriculum"},
    )


@admin.action(description="Attach / update college on selected courses")
def update_college(modeladmin, request, queryset):
    """Bulk-set the college FK on Course rows."""

    class _CollegeForm(forms.Form):
        """Collect the target college for the bulk update.

        Like _CurriculumForm, this form stores the selection in
        _selected_action so the action can update the chosen course rows on
        submission.
        """

        _selected_action = forms.CharField(widget=forms.MultipleHiddenInput)
        college = forms.ModelChoiceField(
            queryset=College.objects.all(),
            label="College to apply",
        )

    if "apply" in request.POST:
        form = _CollegeForm(request.POST)
        if form.is_valid():
            college = form.cleaned_data["college"]
            updated = queryset.update(college=college)
            modeladmin.message_user(
                request,
                f"{updated} course(s) were linked to {college}.",
                messages.SUCCESS,
            )
            return redirect(request.get_full_path())
    else:
        form = _CollegeForm(
            initial={"_selected_action": request.POST.getlist(ACTION_CHECKBOX_NAME)}
        )

    return render(
        request,
        "admin/update_college.html",
        dict(items=queryset, form=form, title="Bulk-set college"),
    )
