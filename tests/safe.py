"""Checks invariants for role/college defaults."""

from django.test import SimpleTestCase

from app.shared.constants.perms import DEFAULT_ROLE_TO_COLLEGE

USER_ROLES = [
    "dean",
    "chair",
    "lecturer",
    "assistant_professor",
    "associate_professor",
    "professor",
    "technician",
    "lab_technician",
    "faculty",
]


class RoleMappingTest(SimpleTestCase):
    def test_mapping_is_consistent(self) -> None:
        """Ensure the default mapping stays aligned with ``USER_ROLES``."""

        # No duplicated keys in the mapping
        self.assertEqual(len(DEFAULT_ROLE_TO_COLLEGE), len(set(DEFAULT_ROLE_TO_COLLEGE)))

        # Every expected role has an entry
        for role in USER_ROLES:
            self.assertIn(role, DEFAULT_ROLE_TO_COLLEGE)

        # Mapping does not contain unexpected roles
        self.assertEqual(set(USER_ROLES), set(DEFAULT_ROLE_TO_COLLEGE))
