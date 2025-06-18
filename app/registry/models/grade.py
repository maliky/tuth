"""Grade records for completed course sections."""

from django.db import models


class Grade(models.Model):
    """Letter/numeric grade awarded to a student for a Section.

    Example:
        >>> from app.registry.models import Grade
        >>> Grade.objects.create(
        ...     student=student_profile,   # check test factories
        ...     section=section_factory(1),
        ...     letter_grade="A",
        ...     numeric_grade=95,
        ... )
    """

    student = models.ForeignKey("people.Student", on_delete=models.CASCADE)
    section = models.ForeignKey("timetable.Section", on_delete=models.CASCADE)
    letter_grade = models.CharField(max_length=2)  # A+, A, B, etc.
    numeric_grade = models.DecimalField(max_digits=4, decimal_places=1)  # e.g., 85.5
    graded_on = models.DateField(auto_now_add=True)

    class Meta:
        unique_together = ("student", "section")

    def __str__(self) -> str:  # pragma: no cover
        """Human readable representation used in admin lists."""
        return f"{self.student} – {self.section}: {self.letter_grade}"
