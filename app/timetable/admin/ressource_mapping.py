"""Column name mappings for import resources in timetable."""

# See 25-26s2_processed_schedule.tsv
PSCHEDULE_HEADER_MAP = {
    "instructor": "faculty",  # "YANCY, George H."
    "location": "room",  # "AC-30"
    "weekday": "schedule_weekday",  # "Monday"
    "cid": "course_shortcode",  # 	"ACCT_102_s1" ,
    "credit": "credit",  # 3
    "course_title": "course_t# can be defaultitle",  # "Introduction to Accounting"
    "college": "college",  # "COBA"
    "start_time": "start_time",  # "08:00"
    "end_time": "end_time",  # "09:30"
}
SCHEDULE_HEADER_MAP = {
    "weekday": "weekday",
    "start_time": "start_time",
    "end_time": "end_time",
}

# to secsession
SECSESSION_HEADER_MAP = {
    "room": "room",   # room, + space
    "schedule": "schedule",  # weekday + start_time, end_time
    "section": "section",  # section_no + course/curriculum (course_no, course_dept, college_code, course_title, credit_hours, is_required) semester_no, academic_year, faculty (username + "prefix", "first", "middle", "last", "suffix"|name)
}

# to section
SECTION_HEADER_MAP = {
    "semester": "semester",
    "curriculum": "curriculum",
    "number": "number",
    "faculty": "faculty",
    "start_date": "start",  # can be default
    "end_date": "end",  # can be default
    "max_seat": "max",
}

# sessions_25-26s1.csv
# "25-26",1,"CAFS","BSc Agriculture","Agricultural Economics","AGR",201,1,3,"SAPEC","SAPEC","Mr. Mustapha Swi","Tuesday","09:40","11:10",,
# for sections
FSESSION_HEADER_MAP = {
    "academic_year": "academic_year",  # "25-26"
    "semester_no": "semester_no",  # 1
    "college_code": "college_code",  # CAFS
    "curriculum": "curriculum",  # ,"BSc Agriculture"
    "course_title": "course_title",  # ,"Practicum I",
    "course_dept": "course_dept",  # AGR
    "course_no": "course_no",  # 121
    "section_no": "section_no",  # 1
    "credit_hours": "credit_hours",  # 1
    "space": "space",  # SAPEC
    "room": "room",  # SAPEC
    "faculty": "faculty",  # "Mr. Dawolor Kanasuah"
    "weekday": "weekday",  # "Friday"
    "start_time": "start_time",  # "09:00"
    "end_time": "end_time",  # "10:00"
    "student_id": "student_id",
    "student_name": "student_name",
}


