from django.db import models


class Grade(models.Model):
    student = models.ForeignKey("people.StudentProfile", on_delete=models.CASCADE)
    section = models.ForeignKey("timetable.Section", on_delete=models.CASCADE)
    letter_grade = models.CharField(max_length=2)  # A+, A, B, etc.
    numeric_grade = models.DecimalField(max_digits=4, decimal_places=1)  # e.g., 85.5
    graded_on = models.DateField(auto_now_add=True)

    class Meta:
        unique_together = ("student", "section")

    def __str__(self):
        return f"{self.student} – {self.section}: {self.letter_grade}"
