from django.contrib import admin

from app.timetable.models import Section, Semester


class SemesterInline(admin.TabularInline):
    model = Semester
    extra = 0
    max_num = 3
    fields = ("number", "start_date", "end_date")
    ordering = ("start_date",)


class SectionInline(admin.TabularInline):
    model = Section
    extra = 0
    fields = ("number", "semester", "instructor", "room", "max_seats")
    ordering = ("semester__start_date", "number")
