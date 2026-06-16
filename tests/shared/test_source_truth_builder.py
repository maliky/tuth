"""Tests for the read-only source-truth builder."""

from __future__ import annotations

import csv
import sqlite3
from pathlib import Path

from app.shared.source_truth.builder import TruthBuildConfigT, build_tusis_truth
from app.shared.source_truth.inventory import (
    build_smartschool_integrity,
    ok_smartschool_tables,
)


def _write(path: Path, text: str) -> None:
    """Write test fixture text."""
    path.parent.mkdir(parents=True, exist_ok=True)
    path.write_text(text, encoding="utf-8")


def _read_tsv(path: Path) -> list[dict[str, str]]:
    """Read a generated TSV report."""
    with path.open(newline="", encoding="utf-8") as handle:
        return list(csv.DictReader(handle, delimiter="\t"))


def test_verified_reexport_counts_override_stale_smartschool_manifest(
    tmp_path: Path,
) -> None:
    """Verified no-sequential re-export counts should make latest CSV usable."""
    smartschool = tmp_path / "smartschool"
    _write(
        smartschool / "_table_manifest.csv",
        "schema_name,table_name,row_count\ndbo,UM_GradeSheet,1\n",
    )
    _write(
        smartschool / "_reexport_attempts_no_sequential.csv",
        "timestamp,schema,table,status,expected_rows,written_rows,attempt,message,file\n"
        "2026-06-08T18:42:06,dbo,UM_GradeSheet,OK,2,2,1,Export verified,x\n",
    )
    _write(
        smartschool / "dbo_UM_GradeSheet.csv",
        "StudentID,Grade\n100,A\n101,B\n",
    )

    integrity = build_smartschool_integrity(smartschool)

    assert integrity[0]["status"] == "ok_verified_reexport"
    assert integrity[0]["selected_source"] == "latest_smartschool"
    assert "UM_GradeSheet" in ok_smartschool_tables(integrity)


def test_build_tusis_truth_flags_broken_latest_and_builds_fuzzy_outputs(
    tmp_path: Path,
) -> None:
    """Broken latest SmartSchool exports fall back while fuzzy reports are built."""
    smartschool = tmp_path / "smartschool"
    fundamentals = tmp_path / "fundamentals"
    grapro = tmp_path / "grapro"
    tucurricula = tmp_path / "tucurricula_import"
    output = tmp_path / "out"

    _write(
        smartschool / "_table_manifest.csv",
        "\ufeffschema_name,table_name,row_count\n"
        "dbo,UM_Courses,1\n"
        "dbo,UM_CoursesLevels,1\n"
        "dbo,payments,1\n",
    )
    _write(smartschool / "dbo_UM_Courses.csv", "\ufeff")
    _write(smartschool / "dbo_UM_CoursesLevels.csv", "\ufeff")
    _write(
        smartschool / "dbo_payments.csv",
        "AcademicYear,Semester,Reference,Date,StudentID,Amount,PaymentType,Donor,Sysref\n"
        "2025/2026,1,R1,2026-01-02,100,50.00,CASH,,SYS1\n",
    )
    _write(
        fundamentals / "academic_course.csv",
        "course_dept,course_no,college_code,course_title,credit_hours\n"
        "CSE,101,COET,Introduction to Computers,3\n",
    )
    _write(
        fundamentals / "academics_curriculums.csv",
        "EnrollmentType\nBSc Computer Science\n",
    )
    _write(
        fundamentals / "academic_curriculum_course.csv",
        "course_dept,course_no,college_code,curriculum\n"
        "CSE,101,COET,BSc Computer Science\n",
    )
    _write(
        fundamentals / "people_full_student.tsv",
        "student_id\tlong_name\tcurriculum\tcollege_code\tusername\n"
        "100\tJane M Doe\tBSc Computer Science\tCOET\tjdoe\n",
    )
    _write(
        fundamentals / "full_grades.tsv",
        "academic_year\tsemester\tstudent_id\tcourse_dept\tcourse_no\tsection_no\t"
        "grade_code\tcredit_hours\tcurriculum\tcollege_code\n"
        "2025/2026\t1\t100\tCSE\t101\t1\tA\t3\tBSc Computer Science\tCOET\n",
    )
    _write(
        fundamentals / "registry_registration.csv",
        "student_id,academic_year,semester,college,major,curriculum\n"
        "100,2025/2026,1,COET,Computer Science,BSc Computer Science\n",
    )
    _write(fundamentals / "finance_payments.csv", "student_id\tamount\n100\t40\n")
    _write(
        grapro / "Courses.csv",
        "CourseID,CourseName,CourseDescription,CreditHours,AreaID\n"
        "CSE 101,Introduction to Computers,Introduction to Computers,3,CSE\n",
    )
    _write(
        grapro / "Accounts.csv",
        "AccountID,FirstName,MiddleName,LastName,AccountType,ProgramID\n"
        "100,Jane,Mary,Doe,Student,BSc Computer Science\n",
    )
    _write(
        tucurricula / "academic_course.tsv",
        "college_code\tcourse_dept\tcourse_no\tcourse_title\tcredit_hours\tdescription\t"
        "source_course_key\n"
        "COET\tCSEN\t101\tIntroduction to Computing\t3\tIntro course\tCSEN101\n",
    )
    _write(
        tucurricula / "academic_curriculum.tsv",
        "college_code\tcurriculum\tlong_name\tstatus\n"
        "COET\tCET-CSEN\tBachelor of Science in Computer Science\tpending\n",
    )
    _write(
        tucurricula / "academic_curriculum_course.tsv",
        "college_code\tcurriculum\tcourse_dept\tcourse_no\tcourse_title\tcredit_hours\t"
        "year_number\tsemester_number\tlevel_number\n"
        "COET\tCET-CSEN\tCSEN\t101\tIntroduction to Computing\t3\t1\t1\t1\n",
    )

    result = build_tusis_truth(
        TruthBuildConfigT(
            smartschool_dir=smartschool,
            fundamentals_dir=fundamentals,
            grapro_csv_dir=grapro,
            grapro_mdb=tmp_path / "missing.mdb",
            tucurricula_import_dir=tucurricula,
            output_dir=output,
        )
    )

    assert result.output_dir == output
    integrity = _read_tsv(output / "table_integrity.tsv")
    um_courses = [row for row in integrity if row["table_name"] == "UM_Courses"][0]
    assert um_courses["status"] == "empty_export_for_nonempty_manifest"
    assert um_courses["selected_source"] == "fallback_required"

    aliases = _read_tsv(output / "course_alias_candidates.tsv")
    assert any(
        row["source_course_key"] == "CSE101" and row["target_course_key"] == "CSEN101"
        for row in aliases
    )
    student_matches = _read_tsv(output / "student_identity_matches.tsv")
    assert student_matches[0]["recommendation"] == "exact_student_id"

    payments = _read_tsv(output / "import_ready" / "finance_payments.tsv")
    assert payments[0]["student_id"] == "100"
    assert "source_name" not in payments[0]

    courses = _read_tsv(output / "import_ready" / "academic_course.tsv")
    course_keys = {row["course_dept"] + row["course_no"] for row in courses}
    assert {"CSEN101", "CSE101"}.issubset(course_keys)
    assert "CET" in {row["college_code"] for row in courses}
    assert "COET" not in {row["college_code"] for row in courses}

    curricula = _read_tsv(output / "import_ready" / "academic_curriculum.tsv")
    historical = [row for row in curricula if row["long_name"] == "BSc Computer Science"]
    assert historical[0]["curriculum"] == "BSc Computer Science"
    assert all(len(row["curriculum"]) <= 40 for row in curricula)

    with sqlite3.connect(output / "truth.sqlite") as conn:
        staged_count = conn.execute("SELECT COUNT(*) FROM witness_rows").fetchone()[0]
    assert staged_count > 0


def test_curriculum_import_codes_are_clamped_for_verbose_historical_labels(
    tmp_path: Path,
) -> None:
    """Verbose historical curriculum names remain import-safe short codes."""
    smartschool = tmp_path / "smartschool"
    fundamentals = tmp_path / "fundamentals"
    grapro = tmp_path / "grapro"
    tucurricula = tmp_path / "tucurricula_import"
    output = tmp_path / "out"
    verbose_program = "Bachelor of Science in Computer Networks and Security Engineering"

    _write(smartschool / "_table_manifest.csv", "schema_name,table_name,row_count\n")
    _write(fundamentals / "academic_course.csv", "course_dept,course_no\nCSE,101\n")
    _write(
        fundamentals / "academics_curriculums.csv", f"EnrollmentType\n{verbose_program}\n"
    )
    _write(
        fundamentals / "academic_curriculum_course.csv",
        f"course_dept,course_no,curriculum\nCSE,101,{verbose_program}\n",
    )
    _write(fundamentals / "people_full_student.tsv", "student_id\n")
    _write(fundamentals / "full_grades.tsv", "student_id\n")
    _write(fundamentals / "registry_registration.csv", "student_id\n")
    _write(fundamentals / "finance_payments.csv", "student_id\n")
    _write(grapro / "Courses.csv", "CourseID\n")
    _write(grapro / "Accounts.csv", "AccountID\n")
    _write(tucurricula / "academic_course.tsv", "course_dept\tcourse_no\n")
    _write(tucurricula / "academic_curriculum.tsv", "curriculum\tlong_name\n")
    _write(
        tucurricula / "academic_curriculum_course.tsv",
        "curriculum\tcourse_dept\tcourse_no\n",
    )

    build_tusis_truth(
        TruthBuildConfigT(
            smartschool_dir=smartschool,
            fundamentals_dir=fundamentals,
            grapro_csv_dir=grapro,
            grapro_mdb=tmp_path / "missing.mdb",
            tucurricula_import_dir=tucurricula,
            output_dir=output,
        )
    )

    curricula = _read_tsv(output / "import_ready" / "academic_curriculum.tsv")
    assert curricula[0]["long_name"] == verbose_program
    assert len(curricula[0]["curriculum"]) <= 40
    assert curricula[0]["curriculum"] != verbose_program


def test_build_tusis_truth_uses_latest_smartschool_operational_exports(
    tmp_path: Path,
) -> None:
    """Latest SmartSchool students, grades, and course registrations feed import files."""
    smartschool = tmp_path / "smartschool"
    fundamentals = tmp_path / "fundamentals"
    grapro = tmp_path / "grapro"
    tucurricula = tmp_path / "tucurricula_import"
    output = tmp_path / "out"

    _write(
        smartschool / "_table_manifest.csv",
        "schema_name,table_name,row_count\n"
        "dbo,UM_Courses,1\n"
        "dbo,UM_CoursesLevels,3\n"
        "dbo,UM_Curriculums,1\n"
        "dbo,UM_CurriculumCourses,2\n"
        "dbo,UM_GradeSheet,1\n"
        "dbo,UM_Oldgrades,0\n"
        "dbo,UM_Programs,1\n"
        "dbo,UM_Registrations,1\n"
        "dbo,UM_Students,2\n"
        "dbo,UM_StudentsCourses,1\n",
    )
    _write(smartschool / "dbo_UM_Courses.csv", "CourseCode,Course\nNURS,Nursing\n")
    _write(
        smartschool / "dbo_UM_CoursesLevels.csv",
        "CourseCode,CourseNo,Description,CreditHours\n"
        "NURS,101,Foundations of Nursing,3.0\n"
        "Math 003,Math 003,Remedial Math,0.0\n"
        "MATH,3,Remedial Mathematics,0.0\n",
    )
    _write(smartschool / "dbo_UM_Curriculums.csv", "Curriculum\nNursing 1\n")
    _write(
        smartschool / "dbo_UM_CurriculumCourses.csv",
        "Curriculum,CourseCode,CourseNo,Semester\n"
        "Nursing 1,NURS,101,1\n"
        "Nursing 1,ME,ME,2\n",
    )
    _write(
        smartschool / "dbo_UM_GradeSheet.csv",
        "AcademicYear,Semester,StudentID,CourseCode,CourseNo,Section,Grade,CrHrs\n"
        "2025/2026,2,03062,NURS,101,1,A,3.0\n",
    )
    _write(
        smartschool / "dbo_UM_Oldgrades.csv",
        "AcademicYear,Semester,StudentID,CourseCode,CourseNo,Grade,CrHrs,Section\n",
    )
    _write(
        smartschool / "dbo_UM_Programs.csv", "ProgramID,Description\nNursing 1,Nursing\n"
    )
    _write(
        smartschool / "dbo_UM_Registrations.csv",
        "StudentID,AcademicYear,Semester,Date,College,Major,EnrollmentType,Scholarship,"
        "SysRef,Reference,Cleared,GradesUploaded\n"
        "03062,2025/2026,2,2026-01-10T00:00:00,CHS,BSN - Nursing,Nursing 1,"
        "No,SR1,REF1,Yes,Yes\n",
    )
    _write(
        smartschool / "dbo_UM_Students.csv",
        "StudentID,FirstName,MiddleName,LastName,Major,College,SemesterOfEntry,"
        "YearOfEntry,DateOfBirth,Sex,EnrollmentType,Scholarship,Enrolled\n"
        "03062,Wrong,,Nurse,BBA - Accounting,CBA,1,2025/2026,1900-01-01T00:00:00,"
        "Female,Business 1,No,Yes\n"
        "03062,Ada,M,Nurse,BSN - Nursing,CHS,1,2025/2026,2000-01-01T00:00:00,"
        "Female,Nursing 1,No,Yes\n",
    )
    _write(
        smartschool / "dbo_UM_StudentsCourses.csv",
        "AcademicYear,Semester,StudentID,CourseCode,CourseNo,Section,CreditHours\n"
        "2025/2026,2,03062,NURS,101,1,3.0\n",
    )

    _write(fundamentals / "academic_course.csv", "course_dept,course_no\n")
    _write(fundamentals / "academics_curriculums.csv", "EnrollmentType\n")
    _write(fundamentals / "academic_curriculum_course.csv", "course_dept,course_no\n")
    _write(fundamentals / "people_full_student.tsv", "student_id\n")
    _write(fundamentals / "full_grades.tsv", "student_id\n")
    _write(fundamentals / "registry_registration.csv", "student_id\n")
    _write(fundamentals / "finance_payments.csv", "student_id\n")
    _write(
        grapro / "Courses.csv",
        "CourseID,CourseName,CourseDescription,CreditHours,AreaID\n"
        "CHEM 101,General Chemistry,General Chemistry,4,CHEM\n",
    )
    _write(
        grapro / "Accounts.csv",
        "AccountID,FirstName,MiddleName,LastName,Sex,BirthDate,AccountType,ProgramID\n"
        "00353,Augustine,B.,Hinneh,M,03/04/21 00:00:00,Student,BSc - General Agr\n",
    )
    _write(
        grapro / "StudentInfo.csv",
        "AccountID,HomeCountry,ClassLevel,TermFirstEntered,TermLastEnrolled,"
        "EnrollmentStatusID\n"
        '00353,LIBERIA,Senior,"2009/2010, 1st Semes","2009/2010, 2nd Semes",G\n',
    )
    _write(
        grapro / "StudentRecords.csv",
        "AccountID,ProgramID,TermID,ItemID,SectionID,Description,FinalGrade,Quantity\n"
        '00353,BSc - General Agr,"2009/2010, 1st Semes",CHEM 101,1.0,'
        "General Chemistry,C,4\n",
    )
    _write(tucurricula / "academic_course.tsv", "course_dept\tcourse_no\nNURS\t101\n")
    _write(
        tucurricula / "academic_curriculum.tsv",
        "college_code\tcurriculum\tlong_name\tstatus\n"
        "CHS\tCHS-NURS\tBachelor of Science in Nursing\tpending\n",
    )
    _write(
        tucurricula / "academic_curriculum_course.tsv",
        "college_code\tcurriculum\tcourse_dept\tcourse_no\tcredit_hours\n"
        "CHS\tCHS-NURS\tNURS\t101\t3\n",
    )
    _write(
        tucurricula / "academic_curriculum_requirement.tsv",
        "curriculum\tcourse_dept\tcourse_no\trequired_course_dept\trequired_course_no\n",
    )

    build_tusis_truth(
        TruthBuildConfigT(
            smartschool_dir=smartschool,
            fundamentals_dir=fundamentals,
            grapro_csv_dir=grapro,
            grapro_mdb=tmp_path / "missing.mdb",
            tucurricula_import_dir=tucurricula,
            output_dir=output,
        )
    )

    students = _read_tsv(output / "import_ready" / "people_full_student.tsv")
    assert students[0]["student_id"] == "03062"
    assert students[0]["first_name"] == "Ada"
    assert students[0]["curriculum"] == "CHS-NURS"
    assert students[0]["legacy_curriculum"] == "BSN - Nursing"
    assert students[0]["last_enrolled_semester"] == "25-26_Sem2"
    grapro_student = [row for row in students if row["student_id"] == "00353"][0]
    assert grapro_student["birth_date"] == "2021-03-04"
    assert grapro_student["entry_semester"] == "09-10_Sem1"

    grades = _read_tsv(output / "import_ready" / "full_grades.tsv")
    assert grades[0]["semester_no"] == "2"
    assert "semester" not in grades[0]
    assert any(
        row["source_row_number"] == "1" and row["course_dept"] == "CHEM" for row in grades
    )
    grapro_grade_actions = _read_tsv(output / "grapro_grade_supplements.tsv")
    assert any(row["action"] == "added_missing" for row in grapro_grade_actions)
    grapro_student_actions = _read_tsv(output / "grapro_student_supplements.tsv")
    assert grapro_student_actions[0]["action"] == "added_missing"

    registrations = _read_tsv(output / "import_ready" / "registry_registration.tsv")
    assert registrations[0]["course_dept"] == "NURS"
    assert registrations[0]["curriculum"] == "BS - Nursing"

    courses = _read_tsv(output / "import_ready" / "academic_course.tsv")
    assert sum(1 for row in courses if row["course_dept"] == "MATH") == 1
    assert not any(row["course_dept"] == "Math 003" for row in courses)
    math_course = [row for row in courses if row["course_dept"] == "MATH"][0]
    assert math_course["course_no"] == "003"

    repairs = _read_tsv(output / "course_identity_repairs.tsv")
    repair_keys = {
        (row["table_name"], row["raw_course_dept"], row["raw_course_no"])
        for row in repairs
    }
    assert ("UM_CoursesLevels", "Math 003", "Math 003") in repair_keys
    assert ("UM_CoursesLevels", "MATH", "3") in repair_keys
    padded = [
        row
        for row in repairs
        if row["raw_course_dept"] == "MATH" and row["raw_course_no"] == "3"
    ][0]
    assert padded["course_no"] == "003"
    assert padded["repair_reason"] == "legacy_padded_number"

    invalid_courses = _read_tsv(output / "invalid_course_identity_rows.tsv")
    assert invalid_courses[0]["table_name"] == "UM_CurriculumCourses"
    assert invalid_courses[0]["raw_course_dept"] == "ME"
    assert invalid_courses[0]["reason"] == "course_number_has_no_digit"

    semester_enrollments = _read_tsv(
        output / "import_ready" / "registry_semester_enrollment.tsv"
    )
    assert semester_enrollments[0]["student_id"] == "03062"
    assert "course_dept" not in semester_enrollments[0]

    curricula = _read_tsv(output / "import_ready" / "academic_curriculum.tsv")
    revised = [row for row in curricula if row["curriculum"] == "CHS-NURS"][0]
    assert revised["status"] == "approved"
    assert revised["is_active"] == "true"

    runbook = (output / "IMPORT_RUNBOOK.org").read_text(encoding="utf-8")
    assert runbook.count("#+begin_src bash") == 5
    assert "registry_semester_enrollment.tsv is audit-only" in runbook
    assert "extract_tucurricula_imports.py" in runbook
    assert "backfill_registration_invoices --academic-year 25-26" in runbook
