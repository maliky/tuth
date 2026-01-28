-- Pre-merge conflict checks for hard curriculum merges.
-- Usage (psql/dbshell):
--   \set source_id 1
--   \set target_id 2
--   \i scripts/curriculum_merge_conflicts.sql

-- Confirm the selected curricula.
SELECT id, short_name, long_name, code
FROM academics_curriculum
WHERE id IN (:source_id, :target_id)
ORDER BY id;

-- Student counts per curriculum.
SELECT curriculum_id, COUNT(*) AS student_count
FROM people_student
WHERE curriculum_id IN (:source_id, :target_id)
GROUP BY curriculum_id
ORDER BY curriculum_id;

-- Courses present in both source and target curricula.
SELECT
    c.id AS course_id,
    c.short_code,
    c.title,
    sc.id AS source_curriculum_course_id,
    tc.id AS target_curriculum_course_id,
    sc.is_required AS source_is_required,
    tc.is_required AS target_is_required,
    sc.is_elective AS source_is_elective,
    tc.is_elective AS target_is_elective,
    sc.credit_hours_id AS source_credit_hours,
    tc.credit_hours_id AS target_credit_hours
FROM academics_curriculumcourse AS sc
JOIN academics_curriculumcourse AS tc
  ON tc.course_id = sc.course_id
  AND tc.curriculum_id = :target_id
JOIN academics_course AS c ON c.id = sc.course_id
WHERE sc.curriculum_id = :source_id
ORDER BY c.short_code;

-- Courses in source that are not in target.
SELECT c.id AS course_id, c.short_code, c.title
FROM academics_curriculumcourse AS sc
JOIN academics_course AS c ON c.id = sc.course_id
WHERE sc.curriculum_id = :source_id
  AND NOT EXISTS (
      SELECT 1
      FROM academics_curriculumcourse AS tc
      WHERE tc.curriculum_id = :target_id
        AND tc.course_id = sc.course_id
  )
ORDER BY c.short_code;

-- Section collisions when reparenting to target curriculum courses.
WITH source_sections AS (
    SELECT s.id AS source_section_id,
           s.semester_id,
           s.number AS section_number,
           cc.course_id
    FROM timetable_section AS s
    JOIN academics_curriculumcourse AS cc
      ON cc.id = s.curriculum_course_id
    WHERE cc.curriculum_id = :source_id
),
target_sections AS (
    SELECT s.id AS target_section_id,
           s.semester_id,
           s.number AS section_number,
           cc.course_id
    FROM timetable_section AS s
    JOIN academics_curriculumcourse AS cc
      ON cc.id = s.curriculum_course_id
    WHERE cc.curriculum_id = :target_id
)
SELECT
    src.source_section_id,
    tgt.target_section_id,
    sem.id AS semester_id,
    ay.code AS academic_year,
    sem.number AS semester_number,
    c.short_code AS course_code,
    src.section_number
FROM source_sections AS src
JOIN target_sections AS tgt
  ON tgt.course_id = src.course_id
 AND tgt.semester_id = src.semester_id
 AND tgt.section_number = src.section_number
JOIN timetable_semester AS sem ON sem.id = src.semester_id
JOIN timetable_academicyear AS ay ON ay.id = sem.academic_year_id
JOIN academics_course AS c ON c.id = src.course_id
ORDER BY ay.code, sem.number, c.short_code, src.section_number;

-- Duplicate prerequisites that will collide after merge.
SELECT
    p.course_id,
    c.short_code AS course_code,
    p.prerequisite_course_id,
    pc.short_code AS prereq_code
FROM academics_prerequisite AS p
JOIN academics_prerequisite AS t
  ON t.course_id = p.course_id
 AND t.prerequisite_course_id = p.prerequisite_course_id
 AND t.curriculum_id = :target_id
JOIN academics_course AS c ON c.id = p.course_id
JOIN academics_course AS pc ON pc.id = p.prerequisite_course_id
WHERE p.curriculum_id = :source_id
ORDER BY c.short_code, pc.short_code;

-- Major curriculum links in the source curriculum.
SELECT
    m.id AS major_id,
    m.name AS major_name,
    COUNT(*) AS course_count
FROM academics_major AS m
JOIN academics_majorcurriculumcourse AS mcc ON mcc.major_id = m.id
JOIN academics_curriculumcourse AS cc ON cc.id = mcc.curriculum_course_id
WHERE m.curriculum_id = :source_id
GROUP BY m.id, m.name
ORDER BY m.name;

-- Minor curriculum links in the source curriculum.
SELECT
    m.id AS minor_id,
    m.name AS minor_name,
    COUNT(*) AS course_count
FROM academics_minor AS m
JOIN academics_minorcurriculumcourse AS mcc ON mcc.minor_id = m.id
JOIN academics_curriculumcourse AS cc ON cc.id = mcc.curriculum_course_id
WHERE m.curriculum_id = :source_id
GROUP BY m.id, m.name
ORDER BY m.name;

-- Section registration counts for source curriculum (useful before moving sections).
SELECT
    s.id AS section_id,
    c.short_code AS course_code,
    sem.id AS semester_id,
    sem.number AS semester_number,
    COUNT(r.id) AS registration_count
FROM timetable_section AS s
JOIN academics_curriculumcourse AS cc ON cc.id = s.curriculum_course_id
JOIN academics_course AS c ON c.id = cc.course_id
JOIN timetable_semester AS sem ON sem.id = s.semester_id
LEFT JOIN registry_registration AS r ON r.section_id = s.id
WHERE cc.curriculum_id = :source_id
GROUP BY s.id, c.short_code, sem.id, sem.number
ORDER BY sem.id, c.short_code, s.number;
