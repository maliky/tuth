import pytest
from datetime import date
from app.people.models.role_assignment import RoleAssignment
from app.people.choices import UserRole


@pytest.mark.django_db
def test_role_assignment_crud(user, college):
    """CRUD operations for RoleAssignment."""
    role = RoleAssignment.objects.create(
        user=user,
        role=UserRole.REGISTRAR,
        college=college,
        start_date=date.today(),
    )
    assert RoleAssignment.objects.filter(pk=role.pk).exists()

    fetched = RoleAssignment.objects.get(pk=role.pk)
    assert fetched == role

    fetched.end_date = date.today()
    fetched.save()
    updated = RoleAssignment.objects.get(pk=role.pk)
    assert updated.end_date is not None

    updated.delete()
    assert not RoleAssignment.objects.filter(pk=role.pk).exists()
