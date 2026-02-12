"""Academics proxy model for student-curriculum enrollments."""

from app.people.models.student_curriculum_enrollment import StdCurriEnroll


class CurriStdEnroll(StdCurriEnroll):
    """Expose student-curriculum enrollments under the academics app in admin."""

    class Meta:
        proxy = True
        app_label = "academics"
        verbose_name = "Student Program Enrollment"
        verbose_name_plural = "Student Program Enrolls"
