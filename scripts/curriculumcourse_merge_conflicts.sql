-- Pre-merge conflict checks for hard curriculum course merges.
-- Usage (psql/dbshell):
--   \set source_id 1
--   \set target_id 2
--   \i scripts/curriculumcourse_merge_conflicts.sql

-- Confirm the selected curriculum courses.
WITH src AS (
    SELECT
        cc.id,
        cc.curriculum_id,
        cur.short_name AS curriculum_short_name,
        cc.course_id,
        c.short_code AS course_short_code,
        c.title AS course_title,
        d.code AS dept_code,
        cc.credit_hours_id,
        cc.is_required,
        cc.is_elective
    FROM academics_curricrs AS cc
    JOIN academics_curriculum AS cur ON cur.id = cc.curriculum_id
    JOIN academics_course AS c ON c.id = cc.course_id
    JOIN academics_department AS d ON d.id = c.department_id
    WHERE cc.id = :source_id
),
tgt AS (
    SELECT
        cc.id,
        cc.curriculum_id,
        cur.short_name AS curriculum_short_name,
        cc.course_id,
        c.short_code AS course_short_code,
        c.title AS course_title,
        d.code AS dept_code,
        cc.credit_hours_id,
        cc.is_required,
        cc.is_elective
    FROM academics_curricrs AS cc
    JOIN academics_curriculum AS cur ON cur.id = cc.curriculum_id
    JOIN academics_course AS c ON c.id = cc.course_id
    JOIN academics_department AS d ON d.id = c.department_id
    WHERE cc.id = :target_id
)
SELECT
    'source' AS role,
    src.id AS curriculum_course_id,
    src.curriculum_id,
    src.curriculum_short_name,
    src.course_id,
    src.course_short_code,
    src.course_title,
    src.dept_code,
    src.credit_hours_id,
    src.is_required,
    src.is_elective
FROM src
UNION ALL
SELECT
    'target' AS role,
    tgt.id AS curriculum_course_id,
    tgt.curriculum_id,
    tgt.curriculum_short_name,
    tgt.course_id,
    tgt.course_short_code,
    tgt.course_title,
    tgt.dept_code,
    tgt.credit_hours_id,
    tgt.is_required,
    tgt.is_elective
FROM tgt
ORDER BY role;

-- Section collisions when merging sections onto the target curriculum course.
WITH source_sections AS (
    SELECT
        s.id AS source_section_id,
        s.semester_id,
        s.number AS section_number
    FROM timetable_section AS s
    WHERE s.curriculum_course_id = :source_id
),
target_sections AS (
    SELECT
        s.id AS target_section_id,
        s.semester_id,
        s.number AS section_number
    FROM timetable_section AS s
    WHERE s.curriculum_course_id = :target_id
)
SELECT
    src.source_section_id,
    tgt.target_section_id,
    sem.id AS semester_id,
    ay.code AS academic_year,
    sem.number AS semester_number,
    src.section_number
FROM source_sections AS src
JOIN target_sections AS tgt
  ON tgt.semester_id = src.semester_id
 AND tgt.section_number = src.section_number
JOIN timetable_semester AS sem ON sem.id = src.semester_id
JOIN timetable_academicyear AS ay ON ay.id = sem.academic_year_id
ORDER BY ay.code, sem.number, src.section_number;

-- Invoice collisions when moving invoices to the target curriculum course.
SELECT
    s.id AS source_invoice_id,
    t.id AS target_invoice_id,
    s.student_id,
    s.semester_id
FROM finance_courseinvoice AS s
JOIN finance_courseinvoice AS t
  ON t.student_id = s.student_id
 AND t.semester_id = s.semester_id
WHERE s.curriculum_course_id = :source_id
  AND t.curriculum_course_id = :target_id
ORDER BY s.student_id, s.semester_id;

-- Invoice counts for both curriculum courses.
SELECT
    curriculum_course_id,
    COUNT(*) AS invoice_count
FROM finance_courseinvoice
WHERE curriculum_course_id IN (:source_id, :target_id)
GROUP BY curriculum_course_id
ORDER BY curriculum_course_id;

-- Section counts for both curriculum courses.
SELECT
    curriculum_course_id,
    COUNT(*) AS section_count
FROM timetable_section
WHERE curriculum_course_id IN (:source_id, :target_id)
GROUP BY curriculum_course_id
ORDER BY curriculum_course_id;
