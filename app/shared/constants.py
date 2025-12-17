"""Expose shared constants and enumerations used throughout the project."""

STYLE_DEFAULT = "NOTICE"
APPROVED = "approved"
UNDEFINED_CHOICES = "undefined_choice"

__all__ = [
    "APPROVED",
    "STYLE_DEFAULT",
    "UNDEFINED_CHOICES",
]

DATA_COLUMN_REMAP = {
    "countyoforigin": "origin_county",
    "course_dept_no": "course_dept",
    "course_name": "course_dept",
    "course_title": "title",
    "curriculum_short_name": "major",
    "dateofbirth": "birth_date",
    "dept_code": "course_dept",
    "emergencycontact": "emergency_contact",
    "enrollement_semester": "current_enrolled_sem",
    "fatheraddress": "father_address",
    "fathername": "father_name",
    "firstname": "first_name",
    "gender": "gender",
    "grade": "grade_code",
    "instructor": "faculty",
    "lastname": "last_name",
    "lastschoolattended": "last_school_attended",
    "maritalstatus": "marital_status",
    "middlename": "middle_name",
    "motheraddress": "mother_address",
    "mothername": "mother_name",
    "nameprefix": "name_prefix",
    "namesuffix": "name_suffix",
    "phone": "phone_no",
    "phoneno": "phone_no",
    "phonenumber": "phone_no",
    "placeofbirth": "birth_place",
    "reasonforleaving": "reason_for_leaving",
    "semester": "semester_no",
}
