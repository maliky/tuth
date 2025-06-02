from __future__ import annotations

from django.db import models

from app.shared.enums import WEEKDAYS_NUMBER


class Schedule(models.Model):
    weekday = models.PositiveSmallIntegerField(
        choices=WEEKDAYS_NUMBER.choices, help_text="Week day number (Monday 1...)"
    )
    room = models.ForeignKey(
        "spaces.Room", null=True, blank=True, on_delete=models.SET_NULL
    )
    faculty = models.ForeignKey(
        "people.FacultyProfile",
        null=True,
        blank=True,
        on_delete=models.SET_NULL,
        # > need to fixe people.StaffProfile.user: (fields.E304) Reverse accessor 'User.profile' for 'people.StaffProfile.user' clashes with reverse accessor for 'people.StudentProfile.user'.	HINT: Add or change a related_name argument to the definition for 'people.StaffProfile.user' or 'people.StudentProfile.user'.
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

    start_time = models.TimeField(null=True, blank=True)
    end_time = models.TimeField(null=True, blank=True)

    # > validation end_time should alway be bigger than start_time
