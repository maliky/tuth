-- Collapse duplicate final grades for one student when the grade value matches.
--
-- Scope:
--   - One student only (required psql var: student_id).
--   - Final grades only: A/B/C/D/E.
--   - Dedup key is (canonical_course_code, grade_code):
--       canonical_course_code = UPPER(TRIM(course.short_code)) when present,
--       fallback to UPPER(TRIM(course.code)).
--   - This handles "same short_code, different underlying course id/code" rows.
--
-- Safety:
--   - Dry-run by default (no deletion).
--   - Ambiguous groups (same canonical code + grade but different course numbers)
--     are reported and skipped from deletion.
--
-- Usage (dry-run):
--   cat scripts/dedupe_single_student_same_grade_courses.sql | \
--     docker-compose -f docker-compose-preprod.yml exec -T db \
--     psql -U "$POSTGRES_USER" -d "$POSTGRES_DB" -v student_id=123
--
-- Usage (apply):
--   cat scripts/dedupe_single_student_same_grade_courses.sql | \
--     docker-compose -f docker-compose-preprod.yml exec -T db \
--     psql -U "$POSTGRES_USER" -d "$POSTGRES_DB" -v student_id=123 -v apply=1

\if :{?student_id}
\else
\echo 'ERROR: pass -v student_id=<id>'
\quit 1
\endif

\if :{?apply}
\else
\set apply 0
\endif

BEGIN;

DROP TABLE IF EXISTS tmp_std_grade_basis;
CREATE TEMP TABLE tmp_std_grade_basis AS
SELECT
    g.id AS grade_id,
    g.student_id,
    g.section_id,
    g.value_id,
    LOWER(COALESCE(gv.code, '')) AS grade_code,
    cc.course_id,
    c.number AS course_number,
    UPPER(TRIM(COALESCE(NULLIF(c.short_code, ''), c.code))) AS canonical_course_code,
    UPPER(TRIM(COALESCE(c.short_code, ''))) AS short_code,
    UPPER(TRIM(COALESCE(c.code, ''))) AS course_code,
    COALESCE(sem.start_date, ay.start_date) AS semester_start_date,
    sem.number AS semester_number,
    (
        CASE WHEN s.number = 1 THEN 1 ELSE 0 END
        + CASE WHEN s.faculty_id IS NULL THEN 1 ELSE 0 END
        + CASE WHEN s.start_date IS NULL THEN 1 ELSE 0 END
        + CASE WHEN s.end_date IS NULL THEN 1 ELSE 0 END
        + CASE WHEN COALESCE(NULLIF(TRIM(s.info), ''), '') = '' THEN 1 ELSE 0 END
        + CASE WHEN s.current_registrations = 0 THEN 1 ELSE 0 END
        + CASE WHEN s.max_seats = 30 THEN 1 ELSE 0 END
    ) AS section_default_score,
    s.number AS section_number
FROM registry_grade AS g
JOIN registry_gradevalue AS gv
  ON gv.id = g.value_id
JOIN timetable_section AS s
  ON s.id = g.section_id
JOIN academics_curricourse AS cc
  ON cc.id = s.curriculum_course_id
JOIN academics_course AS c
  ON c.id = cc.course_id
LEFT JOIN timetable_semester AS sem
  ON sem.id = s.semester_id
LEFT JOIN timetable_academicyear AS ay
  ON ay.id = sem.academic_year_id
WHERE g.student_id = :student_id
  AND LOWER(COALESCE(gv.code, '')) IN ('a', 'b', 'c', 'd', 'e');

-- 1) Preview duplicate groups that qualify by same canonical course code + same grade.
WITH duplicate_groups AS (
    SELECT
        canonical_course_code,
        grade_code,
        COUNT(*) AS grade_count,
        COUNT(DISTINCT course_id) AS distinct_course_ids,
        COUNT(DISTINCT course_number) AS distinct_course_numbers,
        ARRAY_AGG(DISTINCT course_id ORDER BY course_id) AS course_ids,
        ARRAY_AGG(DISTINCT course_code ORDER BY course_code) AS course_codes
    FROM tmp_std_grade_basis
    GROUP BY canonical_course_code, grade_code
    HAVING COUNT(*) > 1
)
SELECT
    canonical_course_code,
    grade_code,
    grade_count,
    distinct_course_ids,
    distinct_course_numbers,
    course_ids,
    course_codes
FROM duplicate_groups
ORDER BY canonical_course_code, grade_code;

-- 2) Preview ambiguous groups (different course numbers under the same key+grade).
DROP TABLE IF EXISTS tmp_std_grade_ambiguous_groups;
CREATE TEMP TABLE tmp_std_grade_ambiguous_groups AS
SELECT
    canonical_course_code,
    grade_code,
    COUNT(*) AS grade_count,
    COUNT(DISTINCT course_number) AS distinct_course_numbers,
    ARRAY_AGG(DISTINCT course_number ORDER BY course_number) AS course_numbers
FROM tmp_std_grade_basis
GROUP BY canonical_course_code, grade_code
HAVING COUNT(*) > 1
   AND COUNT(DISTINCT course_number) > 1;

SELECT
    canonical_course_code,
    grade_code,
    grade_count,
    distinct_course_numbers,
    course_numbers
FROM tmp_std_grade_ambiguous_groups
ORDER BY canonical_course_code, grade_code;

-- 3) Build deterministic delete plan for non-ambiguous duplicate groups.
DROP TABLE IF EXISTS tmp_std_grade_dedup_plan;
CREATE TEMP TABLE tmp_std_grade_dedup_plan AS
WITH ranked AS (
    SELECT
        basis.*,
        ROW_NUMBER() OVER (
            PARTITION BY basis.canonical_course_code, basis.grade_code
            ORDER BY
                basis.semester_start_date ASC NULLS LAST,
                basis.semester_number ASC NULLS LAST,
                basis.section_default_score ASC,
                basis.section_number ASC,
                basis.grade_id ASC
        ) AS rn
    FROM tmp_std_grade_basis AS basis
    WHERE NOT EXISTS (
        SELECT 1
        FROM tmp_std_grade_ambiguous_groups AS ambiguous
        WHERE ambiguous.canonical_course_code = basis.canonical_course_code
          AND ambiguous.grade_code = basis.grade_code
    )
),
keepers AS (
    SELECT
        canonical_course_code,
        grade_code,
        grade_id AS keep_grade_id
    FROM ranked
    WHERE rn = 1
),
to_drop AS (
    SELECT
        ranked.grade_id AS drop_grade_id,
        keepers.keep_grade_id,
        ranked.canonical_course_code,
        ranked.grade_code,
        ranked.course_id,
        ranked.course_code,
        ranked.short_code
    FROM ranked
    JOIN keepers
      ON keepers.canonical_course_code = ranked.canonical_course_code
     AND keepers.grade_code = ranked.grade_code
    WHERE ranked.rn > 1
)
SELECT *
FROM to_drop;

SELECT
    (SELECT COUNT(*) FROM tmp_std_grade_basis) AS scanned_final_grade_rows,
    (SELECT COUNT(*) FROM tmp_std_grade_ambiguous_groups) AS ambiguous_groups_skipped,
    (SELECT COUNT(*) FROM tmp_std_grade_dedup_plan) AS planned_delete_rows;

\if :apply
DELETE FROM registry_grade AS grade
USING tmp_std_grade_dedup_plan AS plan
WHERE grade.id = plan.drop_grade_id;

SELECT
    'APPLY MODE: duplicate rows deleted for this student.' AS status,
    COUNT(*) AS deleted_rows
FROM tmp_std_grade_dedup_plan;
\else
SELECT
    'DRY-RUN MODE: no rows deleted. Re-run with -v apply=1 to apply.' AS status,
    COUNT(*) AS planned_delete_rows
FROM tmp_std_grade_dedup_plan;
\endif

COMMIT;
