-- Backfill registry_grade.is_effective with one effective row per (student, course).
--
-- Rule:
--   - Most recent section attempt wins.
--   - Recency order:
--       1) semester start date (desc),
--       2) semester id (desc),
--       3) section id (desc),
--       4) graded_on (desc),
--       5) grade id (desc).
--
-- Usage (dry-run):
--   cat scripts/backfill_grade_is_effective.sql | \
--     docker-compose -f docker-compose-preprod.yml exec -T db \
--     psql -U "$POSTGRES_USER" -d "$POSTGRES_DB"
--
-- Usage (apply):
--   cat scripts/backfill_grade_is_effective.sql | \
--     docker-compose -f docker-compose-preprod.yml exec -T db \
--     psql -U "$POSTGRES_USER" -d "$POSTGRES_DB" -v apply=1

\if :{?apply}
\else
\set apply 0
\endif

BEGIN;

DROP TABLE IF EXISTS tmp_grade_effective_rank;
CREATE TEMP TABLE tmp_grade_effective_rank AS
WITH ranked AS (
    SELECT
        g.id,
        g.student_id,
        cc.course_id,
        ROW_NUMBER() OVER (
            PARTITION BY g.student_id, cc.course_id
            ORDER BY
                COALESCE(sem.start_date, ay.start_date) DESC NULLS LAST,
                sem.id DESC,
                s.id DESC,
                g.graded_on DESC,
                g.id DESC
        ) AS rn
    FROM registry_grade AS g
    JOIN timetable_section AS s
      ON s.id = g.section_id
    JOIN academics_curricrs AS cc
      ON cc.id = s.curriculum_course_id
    LEFT JOIN timetable_semester AS sem
      ON sem.id = s.semester_id
    LEFT JOIN timetable_academicyear AS ay
      ON ay.id = sem.academic_year_id
)
SELECT * FROM ranked;

-- Preview: total (student,course) groups and current mismatch count.
SELECT
    COUNT(*) AS student_course_groups
FROM (
    SELECT student_id, course_id
    FROM tmp_grade_effective_rank
    GROUP BY student_id, course_id
) AS groups;

SELECT
    COUNT(*) AS rows_needing_update
FROM tmp_grade_effective_rank AS r
JOIN registry_grade AS g
  ON g.id = r.id
WHERE g.is_effective IS DISTINCT FROM (r.rn = 1);

\if :apply
UPDATE registry_grade AS g
SET is_effective = (r.rn = 1)
FROM tmp_grade_effective_rank AS r
WHERE g.id = r.id
  AND g.is_effective IS DISTINCT FROM (r.rn = 1);

SELECT
    COUNT(*) AS effective_rows_after_apply
FROM registry_grade
WHERE is_effective = TRUE;
\else
SELECT 'dry-run only; no rows updated' AS note;
\endif

COMMIT;
