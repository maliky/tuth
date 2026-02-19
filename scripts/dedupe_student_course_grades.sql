-- Collapse duplicate grades per (student, course) across curricula/semesters.
--
-- Rule:
--   Keep exactly one grade row for each (student_id, course_id), choosing:
--     1) final letter grade first when present (A/B/C/D/E),
--     2) then earliest semester,
--     3) then section with the fewest default-valued fields,
--     4) then lowest section number,
--     5) then lowest grade id.
--
-- Conflict policy:
--   - If a duplicate group has more than one distinct final letter grade, it is
--     flagged as a true conflict and skipped from auto-delete.
--   - If a duplicate group has only one final letter grade (other rows are
--     non-final placeholders), it is treated as safe and auto-collapsed.
--
-- Notes:
--   - This script only updates/deletes rows in registry_grade.
--   - It does not rewrite grade history tables (simple_history); SQL bypasses ORM hooks.
--   - Run in dry-run mode first, inspect conflict report, then apply.
--
-- Usage (dry-run):
--   cat scripts/dedupe_student_course_grades.sql | \
--     docker-compose -f docker-compose-preprod.yml exec -T db \
--     psql -U "$POSTGRES_USER" -d "$POSTGRES_DB"
--
-- Usage (apply deletes):
--   cat scripts/dedupe_student_course_grades.sql | \
--     docker-compose -f docker-compose-preprod.yml exec -T db \
--     psql -U "$POSTGRES_USER" -d "$POSTGRES_DB" -v apply=1

\if :{?apply}
\else
\set apply 0
\endif

BEGIN;

-- 1) Preview duplicate groups that would be collapsed.
WITH grade_basis AS (
    SELECT
        g.id,
        g.student_id,
        g.section_id,
        g.value_id,
        LOWER(COALESCE(gv.code, '')) AS grade_code,
        CASE
            WHEN LOWER(COALESCE(gv.code, '')) IN ('a', 'b', 'c', 'd', 'e') THEN 1
            ELSE 0
        END AS is_final_grade,
        cc.course_id,
        sem.id AS semester_id,
        COALESCE(sem.start_date, ay.start_date) AS semester_start_date,
        sem.number AS semester_number,
        -- Lower score = richer section metadata (fewer defaults).
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
    JOIN timetable_section AS s
      ON s.id = g.section_id
    JOIN academics_curricrs AS cc
      ON cc.id = s.curriculum_course_id
    LEFT JOIN registry_gradevalue AS gv
      ON gv.id = g.value_id
    LEFT JOIN timetable_semester AS sem
      ON sem.id = s.semester_id
    LEFT JOIN timetable_academicyear AS ay
      ON ay.id = sem.academic_year_id
),
duplicate_groups AS (
    SELECT
        student_id,
        course_id,
        COUNT(*) AS grade_count,
        COUNT(DISTINCT grade_code) AS distinct_code_count,
        COUNT(DISTINCT CASE WHEN is_final_grade = 1 THEN grade_code END)
            AS distinct_final_grade_count
    FROM grade_basis
    GROUP BY student_id, course_id
    HAVING COUNT(*) > 1
)
SELECT
    dg.student_id,
    dg.course_id,
    dg.grade_count,
    dg.distinct_code_count,
    dg.distinct_final_grade_count
FROM duplicate_groups AS dg
ORDER BY dg.student_id, dg.course_id;

-- 2) Preview true conflicts:
--    more than one distinct final letter grade in the same (student, course).
WITH grade_basis AS (
    SELECT
        g.student_id,
        cc.course_id,
        LOWER(COALESCE(gv.code, '')) AS grade_code
    FROM registry_grade AS g
    JOIN timetable_section AS s
      ON s.id = g.section_id
    JOIN academics_curricrs AS cc
      ON cc.id = s.curriculum_course_id
    LEFT JOIN registry_gradevalue AS gv
      ON gv.id = g.value_id
),
true_conflicts AS (
    SELECT
        student_id,
        course_id,
        COUNT(*) AS grade_count,
        ARRAY_AGG(DISTINCT grade_code ORDER BY grade_code) AS grade_codes,
        COUNT(DISTINCT CASE
            WHEN grade_code IN ('a', 'b', 'c', 'd', 'e') THEN grade_code
        END) AS distinct_final_grade_count
    FROM grade_basis
    GROUP BY student_id, course_id
    HAVING COUNT(*) > 1
       AND COUNT(DISTINCT CASE
            WHEN grade_code IN ('a', 'b', 'c', 'd', 'e') THEN grade_code
       END) > 1
)
SELECT
    student_id,
    course_id,
    grade_count,
    distinct_final_grade_count,
    grade_codes
FROM true_conflicts
ORDER BY student_id, course_id;

-- 3) Build deterministic drop -> keep plan (safe groups only).
DROP TABLE IF EXISTS tmp_grade_dedup_plan;
CREATE TEMP TABLE tmp_grade_dedup_plan AS
WITH grade_basis AS (
    SELECT
        g.id,
        g.student_id,
        g.section_id,
        g.value_id,
        LOWER(COALESCE(gv.code, '')) AS grade_code,
        CASE
            WHEN LOWER(COALESCE(gv.code, '')) IN ('a', 'b', 'c', 'd', 'e') THEN 1
            ELSE 0
        END AS is_final_grade,
        cc.course_id,
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
    JOIN timetable_section AS s
      ON s.id = g.section_id
    JOIN academics_curricrs AS cc
      ON cc.id = s.curriculum_course_id
    LEFT JOIN registry_gradevalue AS gv
      ON gv.id = g.value_id
    LEFT JOIN timetable_semester AS sem
      ON sem.id = s.semester_id
    LEFT JOIN timetable_academicyear AS ay
      ON ay.id = sem.academic_year_id
),
pair_stats AS (
    SELECT
        student_id,
        course_id,
        COUNT(*) AS grade_count,
        COUNT(DISTINCT CASE
            WHEN is_final_grade = 1 THEN grade_code
        END) AS distinct_final_grade_count
    FROM grade_basis
    GROUP BY student_id, course_id
    HAVING COUNT(*) > 1
),
safe_pairs AS (
    SELECT
        student_id,
        course_id
    FROM pair_stats
    WHERE distinct_final_grade_count <= 1
),
ranked AS (
    SELECT
        gb.*,
        ROW_NUMBER() OVER (
            PARTITION BY gb.student_id, gb.course_id
            ORDER BY
                CASE WHEN gb.is_final_grade = 1 THEN 0 ELSE 1 END,
                gb.semester_start_date ASC NULLS LAST,
                gb.semester_number ASC NULLS LAST,
                gb.section_default_score ASC,
                gb.section_number ASC,
                gb.id ASC
        ) AS rn
    FROM grade_basis AS gb
    JOIN safe_pairs AS sp
      ON sp.student_id = gb.student_id
     AND sp.course_id = gb.course_id
),
keepers AS (
    SELECT
        student_id,
        course_id,
        id AS keep_grade_id
    FROM ranked
    WHERE rn = 1
),
to_drop AS (
    SELECT
        r.id AS drop_grade_id,
        k.keep_grade_id,
        r.student_id,
        r.course_id,
        r.section_id AS drop_section_id,
        r.value_id AS drop_value_id
    FROM ranked AS r
    JOIN keepers AS k
      ON k.student_id = r.student_id
     AND k.course_id = r.course_id
    WHERE r.rn > 1
)
SELECT *
FROM to_drop;

-- Show summary of planned deletions.
WITH pair_stats AS (
    SELECT
        g.student_id,
        cc.course_id,
        COUNT(*) AS grade_count,
        COUNT(DISTINCT CASE
            WHEN LOWER(COALESCE(gv.code, '')) IN ('a', 'b', 'c', 'd', 'e')
            THEN LOWER(COALESCE(gv.code, ''))
        END) AS distinct_final_grade_count
    FROM registry_grade AS g
    JOIN timetable_section AS s
      ON s.id = g.section_id
    JOIN academics_curricrs AS cc
      ON cc.id = s.curriculum_course_id
    LEFT JOIN registry_gradevalue AS gv
      ON gv.id = g.value_id
    GROUP BY g.student_id, cc.course_id
    HAVING COUNT(*) > 1
)
SELECT
    COUNT(*) FILTER (WHERE ps.distinct_final_grade_count > 1) AS conflict_pairs_skipped,
    COUNT(*) FILTER (WHERE ps.distinct_final_grade_count <= 1) AS safe_pairs_collapsed,
    (SELECT COUNT(*) FROM tmp_grade_dedup_plan) AS grades_to_delete
FROM pair_stats AS ps;

-- 4) Apply or dry-run.
\if :apply
DELETE FROM registry_grade AS g
USING tmp_grade_dedup_plan AS p
WHERE g.id = p.drop_grade_id;

SELECT
    'APPLY MODE: safe duplicate grades deleted; true conflicts skipped.' AS status,
    COUNT(*) AS deleted_rows
FROM tmp_grade_dedup_plan;
\else
SELECT
    'DRY-RUN MODE: no rows deleted. Re-run with -v apply=1 to apply safe merges only.' AS status,
    COUNT(*) AS planned_delete_rows
FROM tmp_grade_dedup_plan;
\endif

COMMIT;
