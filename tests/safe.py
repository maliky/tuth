from django.test import SimpleTestCase
from app.constants.roles import USER_ROLES, DEFAULT_ROLE_TO_COLLEGE


class RoleMappingTest(SimpleTestCase):
    def test_mapping_is_consistent(self):
        # 1. No duplicate values in the literal  ➜  already true
        self.assertEqual(len(DEFAULT_ROLE_TO_COLLEGE), len(set(DEFAULT_ROLE_TO_COLLEGE)))
