"""Actions module."""

# app/academics/admin/actions.py
from django import forms
from django.contrib import admin, messages
from django.contrib.admin.helpers import ACTION_CHECKBOX_NAME
from django.core.exceptions import ValidationError
from django.shortcuts import redirect, render

from app.academics.models.college import College
from app.academics.models.curriculum import Curriculum
from app.academics.models.curriculum_course import CurriculumCourse
from app.academics.models.department import Department
from app.finance.models.fee_stack import CourseFeeStack, FeeStack


@admin.action(description="Bulk update departments")
def update_department(modeladmin, request, queryset):
    """Bulk-update the Department of selected courses."""

    class _DepartmentUpdateForm(forms.Form):
        """The Department for a bulk action."""

        dept = forms.ModelChoiceField(
            queryset=Department.objects.all().order_by("shortname"),
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


@admin.action(description="Attach fee stack(s) to selected courses")
def attach_fee_stacks(modeladmin, request, queryset):
    """Attach one or more fee stacks to selected courses."""

    class HiddenIdListField(forms.MultipleChoiceField):
        def validate(self, value):
            pass

    class _FeeStackAttachForm(forms.Form):
        """Collect fee stacks to attach to the selected courses."""

        _selected_action = HiddenIdListField(widget=forms.MultipleHiddenInput)
        fee_stacks = forms.ModelMultipleChoiceField(
            queryset=FeeStack.objects.all().order_by("name"),
            label="Fee stacks to attach",
            required=True,
        )

    if "apply" in request.POST:
        form = _FeeStackAttachForm(request.POST)
        if form.is_valid():
            selected_stacks = list(form.cleaned_data["fee_stacks"])
            attached_count = 0
            skipped_existing_count = 0
            skipped_invalid_count = 0
            for course in queryset:
                for fee_stack in selected_stacks:
                    if CourseFeeStack.objects.filter(
                        course=course,
                        fee_stack=fee_stack,
                    ).exists():
                        skipped_existing_count += 1
                        continue
                    try:
                        # Keep rule checks centralized in CourseFeeStack.clean().
                        CourseFeeStack.objects.create(
                            course=course,
                            fee_stack=fee_stack,
                        )
                    except ValidationError:
                        skipped_invalid_count += 1
                        continue
                    attached_count += 1

            if attached_count:
                modeladmin.message_user(
                    request,
                    f"Attached {attached_count} course/stack link(s).",
                    level=messages.SUCCESS,
                )
            if skipped_existing_count:
                modeladmin.message_user(
                    request,
                    (
                        f"Skipped {skipped_existing_count} existing course/stack "
                        "link(s)."
                    ),
                    level=messages.INFO,
                )
            if skipped_invalid_count:
                modeladmin.message_user(
                    request,
                    (
                        f"Skipped {skipped_invalid_count} link(s) because fee types "
                        "would duplicate on a course."
                    ),
                    level=messages.WARNING,
                )
            return redirect(request.get_full_path())
    else:
        form = _FeeStackAttachForm(
            initial={
                "_selected_action": request.POST.getlist(
                    admin.helpers.ACTION_CHECKBOX_NAME
                )
            }
        )

    return render(
        request,
        "admin/attach_fee_stacks.html",
        context={
            "courses": queryset,
            "form": form,
            "title": "Attach fee stacks to selected courses",
            "action_checkbox_name": admin.helpers.ACTION_CHECKBOX_NAME,
        },
    )


@admin.action(description="Bulk update level number")
def update_level_number(modeladmin, request, queryset):
    """Bulk-update the level number on selected programmed courses."""

    class HiddenIdListField(forms.MultipleChoiceField):
        def validate(self, value):
            pass  # allow any IDs

    raw_level_choices = CurriculumCourse._meta.get_field("level_number").choices
    level_choices = raw_level_choices if raw_level_choices is not None else ()

    class _LevelNumberForm(forms.Form):
        """Capture level number for the bulk curriculum-course update."""

        _selected_action = HiddenIdListField(widget=forms.MultipleHiddenInput)
        level_number = forms.TypedChoiceField(
            choices=level_choices,
            coerce=int,
            label="Level number to apply",
        )

    if "apply" in request.POST:
        form = _LevelNumberForm(request.POST)
        if form.is_valid():
            level_number = form.cleaned_data["level_number"]
            updated = 0
            for curriculum_course in queryset:
                curriculum_course.level_number = level_number
                # Keep year/semester derived values in sync via model save hook.
                curriculum_course.save(
                    update_fields=["level_number", "year_number", "semester_number"]
                )
                updated += 1
            modeladmin.message_user(
                request,
                f"{updated} programmed course(s) updated to level {level_number}.",
                messages.SUCCESS,
            )
            return redirect(request.get_full_path())
    else:
        form = _LevelNumberForm(
            initial={
                "_selected_action": request.POST.getlist(
                    admin.helpers.ACTION_CHECKBOX_NAME
                )
            }
        )

    return render(
        request,
        "admin/update_level_number.html",
        context={
            "courses": queryset,
            "form": form,
            "title": "Bulk-set level number",
            "action_checkbox_name": admin.helpers.ACTION_CHECKBOX_NAME,
        },
    )
