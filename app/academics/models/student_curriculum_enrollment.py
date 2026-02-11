"""Academics proxy model for student-curriculum enrollments."""

from app.people.models.student_curriculum_enrollment import StudentCurriculumEnrollment


class CurriculumStudentEnrollment(StudentCurriculumEnrollment):
    """Expose student-curriculum enrollments under the academics app in admin."""

    class Meta:
        proxy = True
        app_label = "academics"
        verbose_name = "Student Program Enrollment"
        verbose_name_plural = "Student Program Enrollments"
