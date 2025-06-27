import pytest

from app.academics.models.department import Department


@pytest.mark.django_db
def test_department_crud(department_factory, college_factory):
    # create
    dept = Department.objects.create(
        short_name="MATH",
        full_name="Mathematics",
        college=college_factory(code="COAS"),
    )
    assert Department.objects.filter(pk=dept.pk).exists()

    # read
    fetched = Department.objects.get(pk=dept.pk)
    assert fetched == dept

    # update
    fetched.full_name = "Applied Mathematics"
    fetched.save()
    updated = Department.objects.get(pk=dept.pk)
    assert updated.full_name == "Applied Mathematics"

    # delete
    updated.delete()
    assert not Department.objects.filter(pk=dept.pk).exists()

