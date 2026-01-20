-- Pre-merge conflict checks for hard course merges.
-- Usage (psql/dbshell):
--   \set source_id 1
--   \set target_id 2
--   \i scripts/course_merge_conflicts.sql

-- Confirm the selected courses.
WITH src AS (
    SELECT
        c.id,
        c.short_code,
        c.number,
        c.title,
        c.department_id,
        d.code AS dept_code,
        d.shortname AS dept_shortname,
        d.college_id AS dept_college_id
    FROM academics_course AS c
    JOIN academics_department AS d ON d.id = c.department_id
    WHERE c.id = :source_id
),
tgt AS (
    SELECT
        c.id,
        c.short_code,
        c.number,
        c.title,
        c.department_id,
        d.code AS dept_code,
        d.shortname AS dept_shortname,
        d.college_id AS dept_college_id
    FROM academics_course AS c
    JOIN academics_department AS d ON d.id = c.department_id
    WHERE c.id = :target_id
)
SELECT
    'source' AS role,
    src.id AS course_id,
    src.short_code,
    src.number,
    src.title,
    src.department_id,
    src.dept_code,
    src.dept_shortname,
    src.dept_college_id
FROM src
UNION ALL
SELECT
    'target' AS role,
    tgt.id AS course_id,
    tgt.short_code,
    tgt.number,
    tgt.title,
    tgt.department_id,
    tgt.dept_code,
    tgt.dept_shortname,
    tgt.dept_college_id
FROM tgt
ORDER BY role;

-- Courses sharing the same number inside the source/target departments.
WITH src AS (
    SELECT department_id FROM academics_course WHERE id = :source_id
),
tgt AS (
    SELECT department_id FROM academics_course WHERE id = :target_id
)
SELECT
    d.id AS department_id,
    d.code AS dept_code,
    c.number AS course_number,
    COUNT(*) AS course_count,
    ARRAY_AGG(c.id ORDER BY c.id) AS course_ids
FROM academics_course AS c
JOIN academics_department AS d ON d.id = c.department_id
WHERE d.id IN (
    SELECT department_id FROM src
    UNION
    SELECT department_id FROM tgt
)
GROUP BY d.id, d.code, c.number
HAVING COUNT(*) > 1
ORDER BY d.code, c.number;

-- Curriculum courses that would collide after the course merge.
WITH src_cc AS (
    SELECT id, curriculum_id, is_required, is_elective, credit_hours_id
    FROM academics_curriculumcourse
    WHERE course_id = :source_id
),
tgt_cc AS (
    SELECT id, curriculum_id, is_required, is_elective, credit_hours_id
    FROM academics_curriculumcourse
    WHERE course_id = :target_id
)
SELECT
    cur.id AS curriculum_id,
    cur.short_name,
    src_cc.id AS source_curriculum_course_id,
    tgt_cc.id AS target_curriculum_course_id,
    src_cc.is_required AS source_is_required,
    tgt_cc.is_required AS target_is_required,
    src_cc.is_elective AS source_is_elective,
    tgt_cc.is_elective AS target_is_elective,
    src_cc.credit_hours_id AS source_credit_hours,
    tgt_cc.credit_hours_id AS target_credit_hours
FROM src_cc
JOIN tgt_cc ON tgt_cc.curriculum_id = src_cc.curriculum_id
JOIN academics_curriculum AS cur ON cur.id = src_cc.curriculum_id
ORDER BY cur.short_name;

-- Section collisions after merging curriculum courses on the target course.
WITH source_sections AS (
    SELECT
        s.id AS source_section_id,
        s.semester_id,
        s.number AS section_number,
        cc.curriculum_id
    FROM timetable_section AS s
    JOIN academics_curriculumcourse AS cc
      ON cc.id = s.curriculum_course_id
    WHERE cc.course_id = :source_id
),
target_sections AS (
    SELECT
        s.id AS target_section_id,
        s.semester_id,
        s.number AS section_number,
        cc.curriculum_id
    FROM timetable_section AS s
    JOIN academics_curriculumcourse AS cc
      ON cc.id = s.curriculum_course_id
    WHERE cc.course_id = :target_id
)
SELECT
    src.source_section_id,
    tgt.target_section_id,
    sem.id AS semester_id,
    ay.code AS academic_year,
    sem.number AS semester_number,
    cur.short_name AS curriculum,
    src.section_number
FROM source_sections AS src
JOIN target_sections AS tgt
  ON tgt.curriculum_id = src.curriculum_id
 AND tgt.semester_id = src.semester_id
 AND tgt.section_number = src.section_number
JOIN timetable_semester AS sem ON sem.id = src.semester_id
JOIN timetable_academicyear AS ay ON ay.id = sem.academic_year_id
JOIN academics_curriculum AS cur ON cur.id = src.curriculum_id
ORDER BY ay.code, sem.number, cur.short_name, src.section_number;

-- Prerequisite collisions when moving the source course to the target.
SELECT
    p.id AS source_prerequisite_id,
    t.id AS target_prerequisite_id,
    cur.short_name AS curriculum,
    c.short_code AS course_code,
    pc.short_code AS prerequisite_code
FROM academics_prerequisite AS p
JOIN academics_prerequisite AS t
  ON t.curriculum_id = p.curriculum_id
 AND t.course_id = :target_id
 AND t.prerequisite_course_id = p.prerequisite_course_id
JOIN academics_curriculum AS cur ON cur.id = p.curriculum_id
JOIN academics_course AS c ON c.id = p.course_id
JOIN academics_course AS pc ON pc.id = p.prerequisite_course_id
WHERE p.course_id = :source_id
ORDER BY cur.short_name, prerequisite_code;

-- Collisions when the source course is used as a prerequisite.
SELECT
    p.id AS source_prerequisite_id,
    t.id AS target_prerequisite_id,
    cur.short_name AS curriculum,
    c.short_code AS course_code,
    pc.short_code AS prerequisite_code
FROM academics_prerequisite AS p
JOIN academics_prerequisite AS t
  ON t.curriculum_id = p.curriculum_id
 AND t.prerequisite_course_id = :target_id
 AND t.course_id = p.course_id
JOIN academics_curriculum AS cur ON cur.id = p.curriculum_id
JOIN academics_course AS c ON c.id = p.course_id
JOIN academics_course AS pc ON pc.id = p.prerequisite_course_id
WHERE p.prerequisite_course_id = :source_id
ORDER BY cur.short_name, course_code;

-- Curriculum course counts for the selected courses.
SELECT
    course_id,
    COUNT(*) AS curriculum_course_count
FROM academics_curriculumcourse
WHERE course_id IN (:source_id, :target_id)
GROUP BY course_id
ORDER BY course_id;

-- Section counts for the selected courses.
SELECT
    cc.course_id,
    COUNT(s.id) AS section_count
FROM timetable_section AS s
JOIN academics_curriculumcourse AS cc
  ON cc.id = s.curriculum_course_id
WHERE cc.course_id IN (:source_id, :target_id)
GROUP BY cc.course_id
ORDER BY cc.course_id;
