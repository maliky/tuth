-- Backfill StudentCurriculumEnrollment from existing Student.curriculum FK.
--
-- What it does:
-- 1) Inserts one enrollment row per (student, student.curriculum) when missing.
-- 2) Forces that FK curriculum row to be primary for each student.
-- 3) Clears primary flag on other rows for the same student.
-- 4) Keeps primary row active and copies entry_semester when missing.
--
-- This script is idempotent and safe to re-run.

BEGIN;

-- Guard: fail fast if migrations for the new table are not applied yet.
DO $$
BEGIN
    IF to_regclass('public.people_studentcurriculumenrollment') IS NULL THEN
        RAISE EXCEPTION
            'Table people_studentcurriculumenrollment does not exist. Run migrations first.';
    END IF;
END $$;

-- 1) Insert missing enrollment rows from Student.curriculum.
INSERT INTO people_studentcurriculumenrollment (
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
      FROM people_studentcurriculumenrollment AS e
      WHERE e.student_id = s.id
        AND e.curriculum_id = s.curriculum_id
  );

-- 2) Align flags/semester metadata for rows tied to Student.curriculum.
UPDATE people_studentcurriculumenrollment AS e
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
-- Expect 0 rows: each student with non-null FK curriculum should have exactly one primary row.
-- SELECT
--     e.student_id,
--     COUNT(*) FILTER (WHERE e.is_primary) AS primary_count
-- FROM people_studentcurriculumenrollment AS e
-- JOIN people_student AS s ON s.id = e.student_id
-- WHERE s.curriculum_id IS NOT NULL
-- GROUP BY e.student_id
-- HAVING COUNT(*) FILTER (WHERE e.is_primary) <> 1;
--
-- Expect 0 rows: each student FK curriculum should exist in enrollment table.
-- SELECT s.id, s.curriculum_id
-- FROM people_student AS s
-- WHERE s.curriculum_id IS NOT NULL
--   AND NOT EXISTS (
--       SELECT 1
--       FROM people_studentcurriculumenrollment AS e
--       WHERE e.student_id = s.id
--         AND e.curriculum_id = s.curriculum_id
--   );
