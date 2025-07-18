"""Actions module."""

# app/academics/admin/actions.py
from django import forms
from django.contrib import admin, messages
from django.contrib.admin.helpers import ACTION_CHECKBOX_NAME
from django.shortcuts import redirect, render

from app.academics.models.college import College
from app.academics.models.curriculum import Curriculum


@admin.action(description="Attach / update curriculum on selected prerequisites")
def update_curriculum(modeladmin, request, queryset):
    """Bulk-update the curriculum FK on selected prerequisites.

    Works in two steps:
      1. GET  → show a tiny form asking for the Curriculum.
      2. POST → apply it and send a flash message.
    """

    class _CurriculumForm(forms.Form):
        """Capture the curriculum for the bulk action.

        The form keeps the primary keys of the selected prerequisites in
        _selected_action and exposes a curriculum field for the admin
        user to pick the destination programme.
        """

        _selected_action = forms.CharField(widget=forms.MultipleHiddenInput)
        curriculum = forms.ModelChoiceField(
            queryset=Curriculum.objects.all(),
            label="Curriculum to apply",
        )

    if "apply" in request.POST:  # step-2
        form = _CurriculumForm(request.POST)
        if form.is_valid():
            curriculum = form.cleaned_data["curriculum"]
            updated = queryset.update(curriculum=curriculum)
            modeladmin.message_user(
                request,
                f"{updated} prerequisite(s) were linked to {curriculum}.",
                messages.SUCCESS,
            )
            return redirect(request.get_full_path())
    else:  # step-1
        form = _CurriculumForm(
            initial={"_selected_action": request.POST.getlist(ACTION_CHECKBOX_NAME)}
        )

    return render(
        request,
        "admin/update_curriculum.html",
        dict(items=queryset, form=form, title="Bulk-set curriculum"),
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
