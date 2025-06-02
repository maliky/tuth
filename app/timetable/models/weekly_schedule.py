from __future__ import annotations
from django.db import models


class WeeklySchedule(models.Model):
    dailyschedule = models.ForeignKey(
        DailySchedule, on_delete=models.PROTECT, related_name="dailyschedule"
    )

    


