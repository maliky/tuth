# tests/test_directory_contact_resources
import tablib
import pytest

from app.people.admin.resources import DirectoryContactResource
from app.people.models.staffs import Staff


@pytest.mark.django_db
def test_directory_contact_import_creates_staff():
    ds = tablib.Dataset(headers=["name"])
    ds.append(["Prof. Isaac A. B. Yancy Ph.D."])
    ds.append(["Blayon, O. G."])
    ds.append(["A. J. K. Doe"])

    DirectoryContactResource().import_data(ds, raise_errors=True)

    assert Staff.objects.count() == 3

    s1 = Staff.objects.get(user__username="iyancy")
    assert s1.name_prefix == "Prof"
    assert s1.middle_name == "A. B."
    assert s1.name_suffix == "PhD"
    assert s1.user.first_name == "Isaac"
    assert s1.user.last_name == "Yancy"

    s2 = Staff.objects.get(user__username="oblayon")
    assert s2.user.first_name == "O"
    assert s2.middle_name == "G"
    assert s2.user.last_name == "Blayon"

    s3 = Staff.objects.get(user__username="adoe")
    assert s3.user.first_name == "A"
    assert s3.middle_name == "J. K."
    assert s3.user.last_name == "Doe"
