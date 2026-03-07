"""Actions module."""

# app/academics/admin/actions.py
from typing import Callable, TypeAlias

from django import forms
from django.contrib import admin, messages
from django.contrib.admin.helpers import ACTION_CHECKBOX_NAME
from django.core.exceptions import ValidationError
from django.db import IntegrityError
from django.shortcuts import redirect, render

from app.academics.admin.merges import merge_crss, merge_curri_crs_into_target
from app.academics.models.college import College
from app.academics.models.course import Course
from app.academics.models.curriculum import Curriculum
from app.academics.models.curriculum_course import CurriCrs
from app.academics.models.department import Department
from app.finance.models.fee_stack import CrsFeeStack, FeeStack

CurriUpdateSummaryT: TypeAlias = dict[str, int]


def _empty_dpt_update_summary() -> dict[str, int]:
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
        "sections_rebucketed_sem0": 0,
        "sections_blocked_sem0_overflow": 0,
        "protected_deletes": 0,
    }


def _add_crs_merge_summary(
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
    summary["sections_rebucketed_sem0"] += merge_summary.get(
        "sections_rebucketed_sem0", 0
    )
    summary["sections_blocked_sem0_overflow"] += merge_summary.get(
        "sections_blocked_sem0_overflow", 0
    )
    summary["protected_deletes"] += merge_summary.get("protected_deletes", 0)


def _empty_curri_update_summary() -> CurriUpdateSummaryT:
    """Return default counters for curriculum relink actions."""
    return {
        "moved": 0,
        "already_in_target": 0,
        "merged_duplicates": 0,
        "skipped_invoices": 0,
        "skipped_incompatible": 0,
        "sections_moved": 0,
        "sections_merged": 0,
        "sections_retained_protected": 0,
        "sections_skipped_grade_conflict": 0,
        "sections_rebucketed_sem0": 0,
        "sections_blocked_sem0_overflow": 0,
        "protected_deletes": 0,
        "skipped_missing_target": 0,
    }


def _apply_curri_relink(
    *,
    selected_rows: list[CurriCrs],
    resolve_target_curri: Callable[[CurriCrs], Curriculum | None],
) -> CurriUpdateSummaryT:
    """Relink rows to resolved target curricula with duplicate-safe merge behavior."""
    summary = _empty_curri_update_summary()
    row_target_map: dict[int, Curriculum] = {}
    target_curri_ids: set[int] = set()

    for curriculum_course in selected_rows:
        target_curri = resolve_target_curri(curriculum_course)
        if target_curri is None:
            summary["skipped_missing_target"] += 1
            continue
        row_target_map[curriculum_course.id] = target_curri
        if target_curri.pk is not None:
            target_curri_ids.add(target_curri.pk)

    target_by_pair = {
        (row.curriculum_id, row.course_id): row
        for row in CurriCrs.objects.filter(curriculum_id__in=target_curri_ids)
        .select_related("course")
        .order_by("id")
    }

    for curriculum_course in selected_rows:
        target_curri = row_target_map.get(curriculum_course.id)
        if target_curri is None:
            continue
        if curriculum_course.curriculum_id == target_curri.id:
            summary["already_in_target"] += 1
            target_by_pair.setdefault(
                (target_curri.id, curriculum_course.course_id),
                curriculum_course,
            )
            continue

        duplicate_target = target_by_pair.get(
            (target_curri.id, curriculum_course.course_id)
        )
        if duplicate_target is not None and duplicate_target.pk != curriculum_course.pk:
            merge_summary = merge_curri_crs_into_target(
                duplicate_target,
                curriculum_course,
            )
            summary["merged_duplicates"] += merge_summary["merged"]
            summary["skipped_invoices"] += merge_summary["skipped_invoices"]
            summary["skipped_incompatible"] += merge_summary["skipped_incompatible"]
            summary["sections_moved"] += merge_summary["sections_moved"]
            summary["sections_merged"] += merge_summary["sections_merged"]
            summary["sections_retained_protected"] += merge_summary[
                "sections_retained_protected"
            ]
            summary["sections_skipped_grade_conflict"] += merge_summary[
                "sections_skipped_grade_conflict"
            ]
            summary["sections_rebucketed_sem0"] += merge_summary[
                "sections_rebucketed_sem0"
            ]
            summary["sections_blocked_sem0_overflow"] += merge_summary[
                "sections_blocked_sem0_overflow"
            ]
            summary["protected_deletes"] += merge_summary["protected_deletes"]
            continue

        curriculum_course.curriculum = target_curri
        try:
            curriculum_course.save(update_fields=["curriculum"])
        except IntegrityError:
            duplicate_target = (
                CurriCrs.objects.filter(
                    curriculum=target_curri,
                    course_id=curriculum_course.course_id,
                )
                .exclude(pk=curriculum_course.pk)
                .first()
            )
            if duplicate_target is None:
                continue
            merge_summary = merge_curri_crs_into_target(
                duplicate_target,
                curriculum_course,
            )
            summary["merged_duplicates"] += merge_summary["merged"]
            summary["skipped_invoices"] += merge_summary["skipped_invoices"]
            summary["skipped_incompatible"] += merge_summary["skipped_incompatible"]
            summary["sections_moved"] += merge_summary["sections_moved"]
            summary["sections_merged"] += merge_summary["sections_merged"]
            summary["sections_retained_protected"] += merge_summary[
                "sections_retained_protected"
            ]
            summary["sections_skipped_grade_conflict"] += merge_summary[
                "sections_skipped_grade_conflict"
            ]
            summary["sections_rebucketed_sem0"] += merge_summary[
                "sections_rebucketed_sem0"
            ]
            summary["sections_blocked_sem0_overflow"] += merge_summary[
                "sections_blocked_sem0_overflow"
            ]
            summary["protected_deletes"] += merge_summary["protected_deletes"]
            continue
        target_by_pair[(target_curri.id, curriculum_course.course_id)] = curriculum_course
        summary["moved"] += 1

    return summary


def _notify_curri_relink_result(
    *,
    modeladmin,
    request,
    summary: CurriUpdateSummaryT,
    target_label: str | None = None,
) -> None:
    """Emit consistent feedback messages for curriculum relink actions."""
    if summary["moved"]:
        if target_label:
            modeladmin.message_user(
                request,
                f"{summary['moved']} course(s) were linked to {target_label}.",
                messages.SUCCESS,
            )
        else:
            modeladmin.message_user(
                request,
                (
                    f"{summary['moved']} course(s) were linked to each department "
                    "college default curriculum."
                ),
                messages.SUCCESS,
            )
    if summary["merged_duplicates"]:
        modeladmin.message_user(
            request,
            (
                f"Merged {summary['merged_duplicates']} duplicate curriculum-course row(s) "
                "into existing target rows."
            ),
            messages.SUCCESS,
        )
    if summary["already_in_target"]:
        if target_label:
            modeladmin.message_user(
                request,
                (
                    f"Skipped {summary['already_in_target']} course(s) already linked to "
                    f"{target_label}."
                ),
                messages.INFO,
            )
        else:
            modeladmin.message_user(
                request,
                (
                    f"Skipped {summary['already_in_target']} course(s) already linked "
                    "to their target default curriculum."
                ),
                messages.INFO,
            )
    if summary["skipped_missing_target"]:
        modeladmin.message_user(
            request,
            (
                f"Skipped {summary['skipped_missing_target']} course(s) because "
                "a target curriculum could not be resolved."
            ),
            messages.WARNING,
        )
    if summary["skipped_invoices"]:
        modeladmin.message_user(
            request,
            (
                f"Skipped {summary['skipped_invoices']} duplicate row(s) because "
                "invoice rows still reference them."
            ),
            messages.WARNING,
        )
    if summary["skipped_incompatible"]:
        modeladmin.message_user(
            request,
            (
                f"Skipped {summary['skipped_incompatible']} duplicate row(s) due to "
                "incompatible course identity."
            ),
            messages.WARNING,
        )
    if summary["sections_merged"]:
        modeladmin.message_user(
            request,
            f"Merged {summary['sections_merged']} conflicting section(s).",
            messages.INFO,
        )
    if summary["sections_moved"]:
        modeladmin.message_user(
            request,
            f"Moved {summary['sections_moved']} section(s) to target rows.",
            messages.INFO,
        )
    if summary["sections_retained_protected"]:
        modeladmin.message_user(
            request,
            (
                f"Retained {summary['sections_retained_protected']} section(s) "
                "because related rows are protected."
            ),
            messages.WARNING,
        )
    if summary["sections_skipped_grade_conflict"]:
        modeladmin.message_user(
            request,
            (
                f"Skipped {summary['sections_skipped_grade_conflict']} section merge(s) "
                "due to conflicting grade values."
            ),
            messages.WARNING,
        )
    if summary["sections_rebucketed_sem0"]:
        modeladmin.message_user(
            request,
            (
                "Rebucketed "
                f"{summary['sections_rebucketed_sem0']} sem0 section conflict(s) "
                "into semesters 1..3 before relinking."
            ),
            messages.INFO,
        )
    if summary["sections_blocked_sem0_overflow"]:
        modeladmin.message_user(
            request,
            (
                "Blocked "
                f"{summary['sections_blocked_sem0_overflow']} sem0 conflict(s) "
                "because no free semester slot (1..3) was available."
            ),
            messages.WARNING,
        )
    if summary["protected_deletes"]:
        modeladmin.message_user(
            request,
            (
                f"Retained {summary['protected_deletes']} source curriculum-course row(s) "
                "because delete is protected."
            ),
            messages.WARNING,
        )
    if all(value == 0 for value in summary.values()):
        modeladmin.message_user(
            request,
            "No course changed for this action.",
            messages.INFO,
        )


@admin.action(description="Bulk update departments")
def update_dpt(modeladmin, request, queryset):
    """Bulk-update the Department of selected courses."""

    class _DptUpdateForm(forms.Form):
        """The Department for a bulk action."""

        dept = forms.ModelChoiceField(
            queryset=Department.objects.all().order_by("shortname"),
            label="Departement to be updated to",
        )
        # forms.CharField(label="New Department Code", max_length=20)

    if "apply" in request.POST:
        form = _DptUpdateForm(request.POST)
        if form.is_valid():
            new_dept = form.cleaned_data["dept"]
            summary = _empty_dpt_update_summary()
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
                    merge_summary = merge_crss(collision_target, [course])
                    _add_crs_merge_summary(summary, merge_summary)
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
            if summary["sections_rebucketed_sem0"]:
                modeladmin.message_user(
                    request,
                    (
                        "Rebucketed "
                        f"{summary['sections_rebucketed_sem0']} sem0 section "
                        "conflict(s) into semesters 1..3 before relinking."
                    ),
                    messages.INFO,
                )
            if summary["sections_blocked_sem0_overflow"]:
                modeladmin.message_user(
                    request,
                    (
                        "Blocked "
                        f"{summary['sections_blocked_sem0_overflow']} sem0 "
                        "conflict(s) because no free semester slot (1..3) was "
                        "available."
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
        form = _DptUpdateForm()

    return render(
        request,
        "admin/update_dpt.html",
        context={
            "courses": queryset,
            "form": form,
            "title": "Confirm Department update",
            "action_checkbox_name": admin.helpers.ACTION_CHECKBOX_NAME,
        },
    )


@admin.action(description="Bulk curriculum update")
def update_curri(modeladmin, request, queryset):
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
            summary = _apply_curri_relink(
                selected_rows=list(selected_rows),
                resolve_target_curri=lambda _row: curriculum,
            )
            _notify_curri_relink_result(
                modeladmin=modeladmin,
                request=request,
                summary=summary,
                target_label=str(curriculum),
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
        "admin/update_curri.html",
        context={"courses": queryset, "form": form, "title": "Bulk-set curriculum"},
    )


@admin.action(description="Move to each department's college default curriculum")
def update_curri_to_dpt_college_dft(modeladmin, request, queryset):
    """Relink selected curriculum-course rows to default curricula per department college."""
    selected_rows = list(
        queryset.select_related("course__department__college").order_by("id").all()
    )
    dft_curri_by_college_id: dict[int, Curriculum] = {}

    def _resolve_target(curriculum_course: CurriCrs) -> Curriculum | None:
        dept = getattr(curriculum_course.course, "department", None)
        if dept is None or dept.college_id is None:
            return None
        target_curri = dft_curri_by_college_id.get(dept.college_id)
        if target_curri is not None:
            return target_curri
        # Cache by college to avoid repeated get_or_create calls.
        target_curri = Curriculum.get_dft(def_college=dept.college)
        dft_curri_by_college_id[dept.college_id] = target_curri
        return target_curri

    summary = _apply_curri_relink(
        selected_rows=selected_rows,
        resolve_target_curri=_resolve_target,
    )
    _notify_curri_relink_result(
        modeladmin=modeladmin,
        request=request,
        summary=summary,
    )
    if dft_curri_by_college_id:
        modeladmin.message_user(
            request,
            (
                "Resolved "
                f"{len(dft_curri_by_college_id)} default curriculum target(s) "
                "from selected departments."
            ),
            messages.INFO,
        )
    return redirect(request.get_full_path())


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
                    if CrsFeeStack.objects.filter(
                        course=course,
                        fee_stack=fee_stack,
                    ).exists():
                        skipped_existing_count += 1
                        continue
                    try:
                        # Keep rule checks centralized in CrsFeeStack.clean().
                        CrsFeeStack.objects.create(
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

    raw_level_choices = CurriCrs._meta.get_field("level_number").choices
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
