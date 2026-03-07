-- Backfill CurriculumStudentEnrollment admin records from existing data sources.
-- Physical DB table: people_stdcurrienroll
--
-- What it does:
-- 1) Inserts missing enrollment rows for curricula found in student grades.
--    - Uses earliest graded semester as entry_semester_id when available.
-- 2) Canonicalizes primary enrollment from enrollment-table precedence:
--    - keep existing primary flag when present,
--    - otherwise prefer active rows,
--    - then latest updated row.
-- 3) Keeps primary row active and copies Student.entry_semester when missing.
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

-- 1) Insert missing enrollment rows derived from grades.
--    This captures curricula where a student has grades but no enrollment row yet.
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

-- 2) Canonicalize one primary row per student from enrollment-table precedence.
WITH ranked AS (
    SELECT
        e.id,
        ROW_NUMBER() OVER (
            PARTITION BY e.student_id
            ORDER BY
                e.is_primary DESC,
                e.is_active DESC,
                e.updated_at DESC,
                e.id DESC
        ) AS row_rank
    FROM people_stdcurrienroll AS e
)
UPDATE people_stdcurrienroll AS e
SET
    is_primary = (r.row_rank = 1),
    is_active = CASE
        WHEN r.row_rank = 1 THEN TRUE
        ELSE e.is_active
    END,
    updated_at = NOW()
FROM ranked AS r
WHERE r.id = e.id
  AND (
      e.is_primary IS DISTINCT FROM (r.row_rank = 1)
      OR (
          r.row_rank = 1
          AND e.is_active IS DISTINCT FROM TRUE
      )
  );

-- 3) Fill missing entry_semester from Student metadata when available.
UPDATE people_stdcurrienroll AS e
SET
    entry_semester_id = s.entry_semester_id,
    updated_at = NOW()
FROM people_student AS s
WHERE s.id = e.student_id
  AND e.entry_semester_id IS NULL
  AND s.entry_semester_id IS NOT NULL;

COMMIT;

-- -------- Post-run verification --------
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
-- Expect 0 rows: each student with enrollments has exactly one primary row.
-- SELECT
--     e.student_id,
--     COUNT(*) FILTER (WHERE e.is_primary) AS primary_count
-- FROM people_stdcurrienroll AS e
-- GROUP BY e.student_id
-- HAVING COUNT(*) FILTER (WHERE e.is_primary) <> 1;
