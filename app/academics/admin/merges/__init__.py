"""Academics merge package split by concern."""

from .actions import (
    merge_courses_action,
    merge_courses_by_short_code_action,
    merge_curricula_action,
    merge_curriculum_courses_action,
    merge_departments_action,
)
from .course_merge import (
    merge_courses,
    merge_curriculum_course_into_target,
    merge_curriculum_courses,
)
from .curriculum_merge import (
    list_curriculum_course_conflicts,
    merge_curricula,
    merge_student_enrollment_pair,
    reconcile_student_curriculum_records,
)
from .helpers import (
    CourseIdentityT,
    CourseMergeSummaryT,
    ConflictChoiceByCourseIdT,
    ConflictChoiceT,
    ConflictCurriCoursePairT,
    MERGE_CHOICE_KEEP_SOURCE,
    MERGE_CHOICE_KEEP_TARGET,
    MERGE_CHOICE_MERGE,
    MERGE_CHOICE_SKIP,
    SectionMergeResultT,
    StdCurriRecordMergeSummaryT,
    empty_student_curriculum_record_summary,
    merge_departments,
)

__all__ = [
    "CourseIdentityT",
    "CourseMergeSummaryT",
    "ConflictChoiceByCourseIdT",
    "ConflictChoiceT",
    "ConflictCurriCoursePairT",
    "MERGE_CHOICE_KEEP_SOURCE",
    "MERGE_CHOICE_KEEP_TARGET",
    "MERGE_CHOICE_MERGE",
    "MERGE_CHOICE_SKIP",
    "SectionMergeResultT",
    "StdCurriRecordMergeSummaryT",
    "empty_student_curriculum_record_summary",
    "list_curriculum_course_conflicts",
    "merge_courses",
    "merge_courses_action",
    "merge_courses_by_short_code_action",
    "merge_curriculum_course_into_target",
    "merge_curricula",
    "merge_curricula_action",
    "merge_curriculum_courses",
    "merge_curriculum_courses_action",
    "merge_departments",
    "merge_departments_action",
    "merge_student_enrollment_pair",
    "reconcile_student_curriculum_records",
]
