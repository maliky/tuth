"""Column name mappings for import resources."""

# Incoming headers -> canonical column names used by FacultyResource
FACULTY_COLUMN_MAP = {
    "Instructor": "faculty",
    "name_prefix": "name_prefix",
    "first_n": "first_name",
    "middle_n": "middle_name",
    "last_n": "last_name",
    "name_suffix": "name_suffix",
    "username": "username",
}
