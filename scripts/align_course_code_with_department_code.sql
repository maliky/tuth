-- Align academics_course.code to UPPER(department.code || course.number).
--
-- Safety rules:
--   - Dry-run by default.
--   - If duplicate rows exist for the same (department_id, number), those rows
--     are treated as conflicts and are NOT updated.
--   - Conflicting rows are printed to stdout for manual review.
--
-- Usage (dry-run):
--   cat scripts/align_course_code_with_department_code.sql | \
--     docker-compose -f docker-compose-preprod.yml exec -T db \
--     psql -U "$POSTGRES_USER" -d "$POSTGRES_DB"
--
-- Usage (apply updates):
--   cat scripts/align_course_code_with_department_code.sql | \
--     docker-compose -f docker-compose-preprod.yml exec -T db \
--     psql -U "$POSTGRES_USER" -d "$POSTGRES_DB" -v apply=1

\if :{?apply}
\else
\set apply 0
\endif

BEGIN;

DROP TABLE IF EXISTS tmp_course_code_align_candidates;
CREATE TEMP TABLE tmp_course_code_align_candidates AS
SELECT
    c.id AS course_id,
    c.department_id,
    d.code AS department_code,
    d.shortname AS department_shortname,
    c.number,
    c.code AS current_code,
    UPPER(d.code || c.number) AS expected_code
FROM academics_course AS c
JOIN academics_department AS d
  ON d.id = c.department_id;

DROP TABLE IF EXISTS tmp_course_code_align_conflicts;
CREATE TEMP TABLE tmp_course_code_align_conflicts AS
WITH duplicate_groups AS (
    SELECT
        department_id,
        number,
        COUNT(*) AS duplicate_count
    FROM tmp_course_code_align_candidates
    GROUP BY department_id, number
    HAVING COUNT(*) > 1
)
SELECT
    cand.course_id,
    cand.department_id,
    cand.department_code,
    cand.department_shortname,
    cand.number,
    cand.current_code,
    cand.expected_code,
    grp.duplicate_count
FROM tmp_course_code_align_candidates AS cand
JOIN duplicate_groups AS grp
  ON grp.department_id = cand.department_id
 AND grp.number = cand.number;

-- Conflict rows are logged to stdout here.
SELECT
    course_id,
    department_id,
    department_code,
    department_shortname,
    number,
    current_code,
    expected_code,
    duplicate_count
FROM tmp_course_code_align_conflicts
ORDER BY department_code, number, course_id;

DROP TABLE IF EXISTS tmp_course_code_align_plan;
CREATE TEMP TABLE tmp_course_code_align_plan AS
SELECT
    cand.course_id,
    cand.department_id,
    cand.department_code,
    cand.number,
    cand.current_code,
    cand.expected_code
FROM tmp_course_code_align_candidates AS cand
WHERE cand.current_code IS DISTINCT FROM cand.expected_code
  AND NOT EXISTS (
      SELECT 1
      FROM tmp_course_code_align_conflicts AS conf
      WHERE conf.course_id = cand.course_id
  );

SELECT
    (SELECT COUNT(*) FROM tmp_course_code_align_candidates) AS scanned_rows,
    (SELECT COUNT(*) FROM tmp_course_code_align_conflicts) AS conflict_rows_skipped,
    (SELECT COUNT(*) FROM tmp_course_code_align_plan) AS planned_updates;

\if :apply
UPDATE academics_course AS c
SET code = p.expected_code
FROM tmp_course_code_align_plan AS p
WHERE c.id = p.course_id;

SELECT
    'APPLY MODE: course codes aligned; conflict rows skipped.' AS status,
    COUNT(*) AS updated_rows
FROM tmp_course_code_align_plan;
\else
SELECT
    'DRY-RUN MODE: no rows updated. Re-run with -v apply=1 to apply.' AS status,
    COUNT(*) AS planned_update_rows
FROM tmp_course_code_align_plan;
\endif

COMMIT;
