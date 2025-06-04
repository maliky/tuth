"""Schedule module."""

from __future__ import annotations

from django.db import models

from app.shared.enums import WEEKDAYS_NUMBER


class Schedule(models.Model):
    weekday = models.PositiveSmallIntegerField(
        choices=WEEKDAYS_NUMBER.choices, help_text="Week day number (Monday 1...)"
    )
    start_time = models.TimeField(null=True, blank=True)
    end_time = models.TimeField(null=True, blank=True)
    faculty = models.ForeignKey(
        "people.FacultyProfile",
        null=True,
        blank=True,
        on_delete=models.SET_NULL,
        related_name="faculty",
        # limit_choices_to={
        #     "user__role_assignments__role__in": [
        #         "faculty",
        #         "lecturer",
        #         "assistant_professor",
        #         "dean",
        #         "chair",
        #         "associate_professor",
        #         "professor",
        #         "vpaa",
        #     ]
        # },
    )
    location = models.ForeignKey(
        "spaces.Room", null=True, blank=True, on_delete=models.SET_NULL
    )

    # > validation end_time should alway be bigger than start_time
    # ? need to check that there no overlap. may need to store duration
    # and implement a non overlap function like for semester and terms.
    def clean(self) -> None:
        """Check that the date are correct"""
        if self.end_time is not None:
            if self.start_time:
                assert self.start_time < self.end_time
