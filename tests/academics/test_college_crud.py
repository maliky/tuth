import pytest
from app.academics.choices import CollegeLongNameChoices
from app.academics.models.college import College


@pytest.mark.django_db
def test_college_crud(college_factory):
    # create
    college = college_factory(code="COHS")
    assert College.objects.filter(pk=college.pk).exists()

    # read
    fetched = College.objects.get(pk=college.pk)
    assert fetched == college

    # update
    fetched.code = "COED"
    fetched.long_name = CollegeLongNameChoices.COED.label
    fetched.save()
    updated = College.objects.get(pk=college.pk)
    assert updated.code == "COED"

    # delete
    updated.delete()
    assert not College.objects.filter(pk=college.pk).exists()

