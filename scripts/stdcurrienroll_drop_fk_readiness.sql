-- Readiness checks before dropping people_student.curriculum_id.
-- This script is read-only and safe to run repeatedly.
--
-- What it validates:
-- 1) Every student has at least one enrollment row.
-- 2) Each student has exactly one primary enrollment row.
-- 3) Existing FK matches primary enrollment when FK is still present.
-- 4) Grade-derived curricula are represented in enrollment rows.

-- 1) Students without any enrollment rows.
SELECT
    'students_without_enrollment' AS check_name,
    COUNT(*)::bigint AS issue_count
FROM people_student AS s
WHERE NOT EXISTS (
    SELECT 1
    FROM people_stdcurrienroll AS e
    WHERE e.student_id = s.id
);

SELECT
    s.id AS student_pk,
    s.student_id
FROM people_student AS s
WHERE NOT EXISTS (
    SELECT 1
    FROM people_stdcurrienroll AS e
    WHERE e.student_id = s.id
)
ORDER BY s.id
LIMIT 50;

-- 2) Students with invalid primary enrollment cardinality.
SELECT
    'students_with_invalid_primary_count' AS check_name,
    COUNT(*)::bigint AS issue_count
FROM (
    SELECT
        e.student_id,
        COUNT(*) FILTER (WHERE e.is_primary) AS primary_count
    FROM people_stdcurrienroll AS e
    GROUP BY e.student_id
    HAVING COUNT(*) FILTER (WHERE e.is_primary) <> 1
) AS invalid_primary;

SELECT
    e.student_id,
    COUNT(*) FILTER (WHERE e.is_primary) AS primary_count,
    COUNT(*) AS enrollment_count
FROM people_stdcurrienroll AS e
GROUP BY e.student_id
HAVING COUNT(*) FILTER (WHERE e.is_primary) <> 1
ORDER BY e.student_id
LIMIT 50;

-- 3) Students where FK and primary enrollment disagree (transitional check).
SELECT
    'fk_primary_mismatch' AS check_name,
    COUNT(*)::bigint AS issue_count
FROM people_student AS s
JOIN people_stdcurrienroll AS e
  ON e.student_id = s.id
 AND e.is_primary
WHERE s.curriculum_id IS NOT NULL
  AND s.curriculum_id <> e.curriculum_id;

SELECT
    s.id AS student_pk,
    s.student_id,
    s.curriculum_id AS fk_curriculum_id,
    e.curriculum_id AS primary_curriculum_id
FROM people_student AS s
JOIN people_stdcurrienroll AS e
  ON e.student_id = s.id
 AND e.is_primary
WHERE s.curriculum_id IS NOT NULL
  AND s.curriculum_id <> e.curriculum_id
ORDER BY s.id
LIMIT 50;

-- 4) Grade-derived curricula missing from enrollment rows.
WITH grade_curriculum_pairs AS (
    SELECT DISTINCT
        g.student_id,
        cc.curriculum_id
    FROM registry_grade AS g
    JOIN timetable_section AS sec
      ON sec.id = g.section_id
    JOIN academics_curricrs AS cc
      ON cc.id = sec.curriculum_course_id
    WHERE cc.curriculum_id IS NOT NULL
)
SELECT
    'missing_grade_curriculum_enrollment' AS check_name,
    COUNT(*)::bigint AS issue_count
FROM grade_curriculum_pairs AS gp
WHERE NOT EXISTS (
    SELECT 1
    FROM people_stdcurrienroll AS e
    WHERE e.student_id = gp.student_id
      AND e.curriculum_id = gp.curriculum_id
);

WITH grade_curriculum_pairs AS (
    SELECT DISTINCT
        g.student_id,
        cc.curriculum_id
    FROM registry_grade AS g
    JOIN timetable_section AS sec
      ON sec.id = g.section_id
    JOIN academics_curricrs AS cc
      ON cc.id = sec.curriculum_course_id
    WHERE cc.curriculum_id IS NOT NULL
)
SELECT
    gp.student_id,
    gp.curriculum_id
FROM grade_curriculum_pairs AS gp
WHERE NOT EXISTS (
    SELECT 1
    FROM people_stdcurrienroll AS e
    WHERE e.student_id = gp.student_id
      AND e.curriculum_id = gp.curriculum_id
)
ORDER BY gp.student_id, gp.curriculum_id
LIMIT 50;
