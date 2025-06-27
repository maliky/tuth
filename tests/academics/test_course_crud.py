from app.academics.models.course import Course
from app.academics.models.department import Department
import pytest

from app.people.models.student import Student
from app.timetable.models.semester import Semester


@pytest.mark.django_db
def test_course_crud_all(student: Student, semester: Semester):
    """We test that if a course A is a prerequisite to course B.
    
    then A must be passed to see B in allowed courses for the student.
    """
    course_a = Course.objects.create(number="101", department=Department.get_default('D1'))
    course_b = Course.objects.create(number="102", department=Department.get_default('D2'))

    
