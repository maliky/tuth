from app.shared.constants.roles import DEFAULT_ROLE_TO_COLLEGE, USER_ROLES
from django.test import SimpleTestCase


class RoleMappingTest(SimpleTestCase):
    def test_mapping_is_consistent(self):
        # 1. No duplicate values in the literal  ➜  already true
        self.assertEqual(len(DEFAULT_ROLE_TO_COLLEGE), len(set(DEFAULT_ROLE_TO_COLLEGE)))
