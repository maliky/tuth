"""Actions module."""

# app/academics/admin/actions.py
from django import forms
from django.contrib import admin, messages
from django.contrib.admin.helpers import ACTION_CHECKBOX_NAME
from django.core.exceptions import ValidationError
from django.db import IntegrityError
from django.shortcuts import redirect, render

from app.academics.admin.merges import merge_courses, merge_curriculum_course_into_target
from app.academics.models.college import College
from app.academics.models.course import Course
from app.academics.models.curriculum import Curriculum
from app.academics.models.curriculum_course import CurriCourse
from app.academics.models.department import Department
from app.finance.models.fee_stack import CourseFeeStack, FeeStack


def _empty_department_update_summary() -> dict[str, int]:
    """Return default counters for the bulk department update action."""
    return {
        "updated": 0,
        "merged_collisions": 0,
        "already_in_target": 0,
        "skipped_invoices": 0,
        "prerequisites_skipped": 0,
        "sections_merged": 0,
        "sections_retained_protected": 0,
        "sections_skipped_grade_conflict": 0,
        "protected_deletes": 0,
    }


def _add_course_merge_summary(
    summary: dict[str, int], merge_summary: dict[str, int]
) -> None:
    """Accumulate relevant merge counters into department action counters."""
    summary["merged_collisions"] += merge_summary.get("merged", 0)
    summary["skipped_invoices"] += merge_summary.get("skipped_invoices", 0)
    summary["prerequisites_skipped"] += merge_summary.get("prerequisites_skipped", 0)
    summary["sections_merged"] += merge_summary.get("sections_merged", 0)
    summary["sections_retained_protected"] += merge_summary.get(
        "sections_retained_protected", 0
    )
    summary["sections_skipped_grade_conflict"] += merge_summary.get(
        "sections_skipped_grade_conflict", 0
    )
    summary["protected_deletes"] += merge_summary.get("protected_deletes", 0)


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
            summary = _empty_department_update_summary()
            selected_ids = list(queryset.order_by("id").values_list("id", flat=True))
            # Keep a lookup of existing target department courses by number so we
            # can merge collisions instead of violating unique constraints.
            target_by_number = {
                course.number: course
                for course in Course.objects.filter(department=new_dept).order_by("id")
            }
            for course_id in selected_ids:
                course = Course.objects.filter(pk=course_id).first()
                if course is None:
                    continue
                if course.department_id == new_dept.id:
                    target_by_number.setdefault(course.number, course)
                    summary["already_in_target"] += 1
                    continue
                collision_target = target_by_number.get(course.number)
                if collision_target is not None and collision_target.pk != course.pk:
                    # Reuse the shared merge path so section/grade dedupe and
                    # conflict reporting stay consistent with other admin merges.
                    merge_summary = merge_courses(collision_target, [course])
                    _add_course_merge_summary(summary, merge_summary)
                    continue
                course.department = new_dept
                course.code = ""
                course.short_code = ""
                course.save(update_fields=["department", "code", "short_code"])
                target_by_number[course.number] = course
                summary["updated"] += 1

            if summary["updated"]:
                modeladmin.message_user(
                    request,
                    f"Moved {summary['updated']} course(s) to {new_dept}.",
                    messages.SUCCESS,
                )
            if summary["merged_collisions"]:
                modeladmin.message_user(
                    request,
                    (
                        "Merged "
                        f"{summary['merged_collisions']} colliding course(s) "
                        f"into existing {new_dept} course(s)."
                    ),
                    messages.SUCCESS,
                )
            if summary["already_in_target"]:
                modeladmin.message_user(
                    request,
                    (
                        f"Skipped {summary['already_in_target']} course(s) already "
                        f"linked to {new_dept}."
                    ),
                    messages.INFO,
                )
            if summary["skipped_invoices"]:
                modeladmin.message_user(
                    request,
                    (
                        f"Skipped {summary['skipped_invoices']} collision merge(s) "
                        "because source curriculum courses have invoices."
                    ),
                    messages.WARNING,
                )
            if summary["sections_merged"]:
                modeladmin.message_user(
                    request,
                    f"Merged {summary['sections_merged']} section conflict(s).",
                    messages.INFO,
                )
            if summary["prerequisites_skipped"]:
                modeladmin.message_user(
                    request,
                    (
                        f"Skipped {summary['prerequisites_skipped']} duplicate "
                        "prerequisite row(s)."
                    ),
                    messages.INFO,
                )
            if summary["sections_skipped_grade_conflict"]:
                modeladmin.message_user(
                    request,
                    (
                        "Skipped "
                        f"{summary['sections_skipped_grade_conflict']} section "
                        "merge(s) because overlapping students had different "
                        "grade values."
                    ),
                    messages.WARNING,
                )
            if summary["sections_retained_protected"]:
                modeladmin.message_user(
                    request,
                    (
                        "Retained "
                        f"{summary['sections_retained_protected']} section(s) "
                        "because grades still protect them."
                    ),
                    messages.WARNING,
                )
            if summary["protected_deletes"]:
                modeladmin.message_user(
                    request,
                    (
                        "Could not delete "
                        f"{summary['protected_deletes']} source course(s) because "
                        "protected related rows still exist."
                    ),
                    messages.WARNING,
                )
            if all(value == 0 for value in summary.values()):
                modeladmin.message_user(
                    request,
                    "No course changed for this action.",
                    messages.INFO,
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

    class _CurriForm(forms.Form):
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
        form = _CurriForm(request.POST)
        if form.is_valid():
            curriculum = form.cleaned_data["curriculum"]
            selected_ids = form.cleaned_data["_selected_action"]
            selected_rows = (
                queryset.model.objects.filter(pk__in=selected_ids)
                .select_related("course")
                .order_by("id")
            )
            moved = 0
            already_in_target = 0
            merged_duplicates = 0
            skipped_invoices = 0
            skipped_incompatible = 0
            sections_moved = 0
            sections_merged = 0
            sections_retained_protected = 0
            sections_skipped_grade_conflict = 0
            protected_deletes = 0
            target_by_course_id = {
                row.course_id: row
                for row in CurriCourse.objects.filter(curriculum=curriculum)
                .select_related("course")
                .order_by("id")
            }
            for curriculum_course in selected_rows:
                if curriculum_course.curriculum_id == curriculum.id:
                    already_in_target += 1
                    continue
                # Auto-merge duplicate rows instead of failing on unique(course, curriculum).
                duplicate_target = target_by_course_id.get(curriculum_course.course_id)
                if (
                    duplicate_target is not None
                    and duplicate_target.pk != curriculum_course.pk
                ):
                    merge_summary = merge_curriculum_course_into_target(
                        duplicate_target,
                        curriculum_course,
                    )
                    merged_duplicates += merge_summary["merged"]
                    skipped_invoices += merge_summary["skipped_invoices"]
                    skipped_incompatible += merge_summary["skipped_incompatible"]
                    sections_moved += merge_summary["sections_moved"]
                    sections_merged += merge_summary["sections_merged"]
                    sections_retained_protected += merge_summary[
                        "sections_retained_protected"
                    ]
                    sections_skipped_grade_conflict += merge_summary[
                        "sections_skipped_grade_conflict"
                    ]
                    protected_deletes += merge_summary["protected_deletes"]
                    continue
                curriculum_course.curriculum = curriculum
                try:
                    curriculum_course.save(update_fields=["curriculum"])
                except IntegrityError:
                    # Safety net for races with concurrent updates.
                    duplicate_target = (
                        CurriCourse.objects.filter(
                            curriculum=curriculum, course_id=curriculum_course.course_id
                        )
                        .exclude(pk=curriculum_course.pk)
                        .first()
                    )
                    if duplicate_target is None:
                        continue
                    merge_summary = merge_curriculum_course_into_target(
                        duplicate_target,
                        curriculum_course,
                    )
                    merged_duplicates += merge_summary["merged"]
                    skipped_invoices += merge_summary["skipped_invoices"]
                    skipped_incompatible += merge_summary["skipped_incompatible"]
                    sections_moved += merge_summary["sections_moved"]
                    sections_merged += merge_summary["sections_merged"]
                    sections_retained_protected += merge_summary[
                        "sections_retained_protected"
                    ]
                    sections_skipped_grade_conflict += merge_summary[
                        "sections_skipped_grade_conflict"
                    ]
                    protected_deletes += merge_summary["protected_deletes"]
                    continue
                target_by_course_id[curriculum_course.course_id] = curriculum_course
                moved += 1
            if moved:
                modeladmin.message_user(
                    request,
                    f"{moved} course(s) were linked to {curriculum}.",
                    messages.SUCCESS,
                )
            if merged_duplicates:
                modeladmin.message_user(
                    request,
                    (
                        f"Merged {merged_duplicates} duplicate curriculum-course row(s) "
                        "into existing target rows."
                    ),
                    messages.SUCCESS,
                )
            if already_in_target:
                modeladmin.message_user(
                    request,
                    (
                        f"Skipped {already_in_target} course(s) already linked to "
                        f"{curriculum}."
                    ),
                    messages.INFO,
                )
            if skipped_invoices:
                modeladmin.message_user(
                    request,
                    (
                        f"Skipped {skipped_invoices} duplicate row(s) because "
                        "invoice rows still reference them."
                    ),
                    messages.WARNING,
                )
            if skipped_incompatible:
                modeladmin.message_user(
                    request,
                    (
                        f"Skipped {skipped_incompatible} duplicate row(s) due to "
                        "incompatible course identity."
                    ),
                    messages.WARNING,
                )
            if sections_merged:
                modeladmin.message_user(
                    request,
                    f"Merged {sections_merged} conflicting section(s).",
                    messages.INFO,
                )
            if sections_moved:
                modeladmin.message_user(
                    request,
                    f"Moved {sections_moved} section(s) to target rows.",
                    messages.INFO,
                )
            if sections_retained_protected:
                modeladmin.message_user(
                    request,
                    (
                        f"Retained {sections_retained_protected} section(s) "
                        "because related rows are protected."
                    ),
                    messages.WARNING,
                )
            if sections_skipped_grade_conflict:
                modeladmin.message_user(
                    request,
                    (
                        f"Skipped {sections_skipped_grade_conflict} section merge(s) "
                        "due to conflicting grade values."
                    ),
                    messages.WARNING,
                )
            if protected_deletes:
                modeladmin.message_user(
                    request,
                    (
                        f"Retained {protected_deletes} source curriculum-course row(s) "
                        "because delete is protected."
                    ),
                    messages.WARNING,
                )
            if (
                moved == 0
                and merged_duplicates == 0
                and already_in_target == 0
                and skipped_invoices == 0
                and skipped_incompatible == 0
                and sections_merged == 0
                and sections_moved == 0
                and sections_retained_protected == 0
                and sections_skipped_grade_conflict == 0
                and protected_deletes == 0
            ):
                modeladmin.message_user(
                    request,
                    "No course changed for this action.",
                    messages.INFO,
                )
            return redirect(request.get_full_path())
        else:
            pass

    else:
        form = _CurriForm(
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

        Like _CurriForm, this form stores the selection in
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

    raw_level_choices = CurriCourse._meta.get_field("level_number").choices
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
