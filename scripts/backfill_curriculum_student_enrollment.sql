-- Backfill CurriculumStudentEnrollment admin records from existing data sources.
-- Physical DB table: people_stdcurrienroll
--
-- What it does:
-- 1) Inserts one enrollment row per (student, student.curriculum) when missing.
-- 2) Inserts missing enrollment rows for curricula found in student grades.
--    - Uses earliest graded semester as entry_semester_id when available.
-- 3) Keeps Student.curriculum authoritative as the primary enrollment.
--    - Exactly that FK curriculum is marked is_primary = TRUE.
--    - Other enrollment rows for the same student are is_primary = FALSE.
-- 4) Keeps primary row active and copies Student.entry_semester when missing.
--
-- This script is idempotent and safe to re-run.

BEGIN;

-- Guard: fail fast if enrollment/grade tables do not exist.
DO $$
BEGIN
    IF to_regclass('public.people_stdcurrienroll') IS NULL THEN
        RAISE EXCEPTION
            'Table people_stdcurrienroll does not exist. Run migrations first.';
    END IF;
    IF to_regclass('public.registry_grade') IS NULL THEN
        RAISE EXCEPTION
            'Table registry_grade does not exist. Check schema/migrations.';
    END IF;
END $$;

-- 1) Insert missing enrollment rows from Student.curriculum.
INSERT INTO people_stdcurrienroll (
    student_id,
    curriculum_id,
    entry_semester_id,
    exit_semester_id,
    is_primary,
    is_active,
    creation_date,
    updated_at
)
SELECT
    s.id,
    s.curriculum_id,
    s.entry_semester_id,
    NULL,
    TRUE,
    TRUE,
    CURRENT_DATE,
    NOW()
FROM people_student AS s
WHERE s.curriculum_id IS NOT NULL
  AND NOT EXISTS (
      SELECT 1
      FROM people_stdcurrienroll AS e
      WHERE e.student_id = s.id
        AND e.curriculum_id = s.curriculum_id
  );

-- 2) Insert missing enrollment rows derived from grades.
--    This captures curricula where a student has grades even if the FK was not set
--    to that curriculum at import time.
WITH grade_curriculum_pairs AS (
    SELECT DISTINCT ON (g.student_id, cc.curriculum_id)
        g.student_id,
        cc.curriculum_id,
        s.semester_id AS entry_semester_id
    FROM registry_grade AS g
    JOIN timetable_section AS s
      ON s.id = g.section_id
    JOIN academics_curricrs AS cc
      ON cc.id = s.curriculum_course_id
    JOIN timetable_semester AS sem
      ON sem.id = s.semester_id
    WHERE cc.curriculum_id IS NOT NULL
    ORDER BY
        g.student_id,
        cc.curriculum_id,
        sem.start_date NULLS LAST,
        sem.id
)
INSERT INTO people_stdcurrienroll (
    student_id,
    curriculum_id,
    entry_semester_id,
    exit_semester_id,
    is_primary,
    is_active,
    creation_date,
    updated_at
)
SELECT
    gp.student_id,
    gp.curriculum_id,
    gp.entry_semester_id,
    NULL,
    FALSE,
    TRUE,
    CURRENT_DATE,
    NOW()
FROM grade_curriculum_pairs AS gp
WHERE NOT EXISTS (
    SELECT 1
    FROM people_stdcurrienroll AS e
    WHERE e.student_id = gp.student_id
      AND e.curriculum_id = gp.curriculum_id
);

-- 3) Align flags/semester metadata for rows tied to Student.curriculum.
UPDATE people_stdcurrienroll AS e
SET
    is_primary = (e.curriculum_id = s.curriculum_id),
    is_active = CASE
        WHEN e.curriculum_id = s.curriculum_id THEN TRUE
        ELSE e.is_active
    END,
    entry_semester_id = COALESCE(e.entry_semester_id, s.entry_semester_id),
    updated_at = NOW()
FROM people_student AS s
WHERE s.id = e.student_id
  AND s.curriculum_id IS NOT NULL;

COMMIT;

-- -------- Post-run verification --------
-- Expect 0 rows: each student FK curriculum should exist in enrollment table.
-- SELECT s.id, s.curriculum_id
-- FROM people_student AS s
-- WHERE s.curriculum_id IS NOT NULL
--   AND NOT EXISTS (
--       SELECT 1
--       FROM people_stdcurrienroll AS e
--       WHERE e.student_id = s.id
--         AND e.curriculum_id = s.curriculum_id
--   );
--
-- Expect 0 rows: each grade-derived curriculum should exist in enrollment table.
-- SELECT
--     g.student_id,
--     cc.curriculum_id,
--     COUNT(*) AS grade_count
-- FROM registry_grade AS g
-- JOIN timetable_section AS s ON s.id = g.section_id
-- JOIN academics_curricrs AS cc ON cc.id = s.curriculum_course_id
-- LEFT JOIN people_stdcurrienroll AS e
--   ON e.student_id = g.student_id
--  AND e.curriculum_id = cc.curriculum_id
-- WHERE cc.curriculum_id IS NOT NULL
--   AND e.id IS NULL
-- GROUP BY g.student_id, cc.curriculum_id
-- ORDER BY g.student_id, cc.curriculum_id;
--
-- Expect 0 rows: each student with non-null FK curriculum has exactly one primary row.
-- SELECT
--     e.student_id,
--     COUNT(*) FILTER (WHERE e.is_primary) AS primary_count
-- FROM people_stdcurrienroll AS e
-- JOIN people_student AS s ON s.id = e.student_id
-- WHERE s.curriculum_id IS NOT NULL
-- GROUP BY e.student_id
-- HAVING COUNT(*) FILTER (WHERE e.is_primary) <> 1;
