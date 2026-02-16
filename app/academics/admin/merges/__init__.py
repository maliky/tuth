"""Academics merge package split by concern."""

from .actions import (
    merge_crss_action,
    merge_crss_by_short_code_action,
    merge_curra_action,
    merge_curri_crss_action,
    merge_dpts_action,
)
from .course_merge import (
    merge_crss,
    merge_curri_crs_into_target,
    merge_curri_crss,
)
from .curriculum_merge import (
    list_curri_crs_conflicts,
    merge_curra,
    merge_std_enrollment_pair,
    reconcile_std_curri_records,
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
    empty_std_curri_record_summary,
    merge_dpts,
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
    "empty_std_curri_record_summary",
    "list_curri_crs_conflicts",
    "merge_crss",
    "merge_crss_action",
    "merge_crss_by_short_code_action",
    "merge_curri_crs_into_target",
    "merge_curra",
    "merge_curra_action",
    "merge_curri_crss",
    "merge_curri_crss_action",
    "merge_dpts",
    "merge_dpts_action",
    "merge_std_enrollment_pair",
    "reconcile_std_curri_records",
]
