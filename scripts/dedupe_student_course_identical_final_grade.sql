-- Collapse duplicate grades only when student + course + final grade are identical.
--
-- Scope:
--   - Final grades are restricted to A/B/C/D/E (F excluded by request).
--   - Semester, curriculum, and course level may differ; they do not block merge.
--   - Non-final grades (IP, NG, W, etc.) are ignored by this script.
--
-- Keep rule inside each duplicate group:
--   1) earliest semester first,
--   2) then section with the fewest default-valued fields,
--   3) then lowest section number,
--   4) then lowest grade id.
--
-- Usage (dry-run):
--   cat scripts/dedupe_student_course_identical_final_grade.sql | \
--     docker-compose -f docker-compose-preprod.yml exec -T db \
--     psql -U "$POSTGRES_USER" -d "$POSTGRES_DB"
--
-- Usage (apply deletes):
--   cat scripts/dedupe_student_course_identical_final_grade.sql | \
--     docker-compose -f docker-compose-preprod.yml exec -T db \
--     psql -U "$POSTGRES_USER" -d "$POSTGRES_DB" -v apply=1

\if :{?apply}
\else
\set apply 0
\endif

BEGIN;

-- 1) Preview duplicate groups by exact (student, course, final grade).
WITH final_grades AS (
    SELECT
        g.id,
        g.student_id,
        cc.course_id,
        LOWER(gv.code) AS grade_code,
        g.section_id,
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
    JOIN academics_curricrs AS cc
      ON cc.id = s.curriculum_course_id
    LEFT JOIN timetable_semester AS sem
      ON sem.id = s.semester_id
    LEFT JOIN timetable_academicyear AS ay
      ON ay.id = sem.academic_year_id
    WHERE LOWER(gv.code) IN ('a', 'b', 'c', 'd', 'e')
),
duplicate_groups AS (
    SELECT
        student_id,
        course_id,
        grade_code,
        COUNT(*) AS grade_count
    FROM final_grades
    GROUP BY student_id, course_id, grade_code
    HAVING COUNT(*) > 1
)
SELECT
    dg.student_id,
    dg.course_id,
    dg.grade_code,
    dg.grade_count
FROM duplicate_groups AS dg
ORDER BY dg.student_id, dg.course_id, dg.grade_code;

-- 2) Build deterministic drop -> keep plan for exact duplicate final-grade groups.
DROP TABLE IF EXISTS tmp_grade_identical_final_dedup_plan;
CREATE TEMP TABLE tmp_grade_identical_final_dedup_plan AS
WITH final_grades AS (
    SELECT
        g.id,
        g.student_id,
        cc.course_id,
        LOWER(gv.code) AS grade_code,
        g.section_id,
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
    JOIN academics_curricrs AS cc
      ON cc.id = s.curriculum_course_id
    LEFT JOIN timetable_semester AS sem
      ON sem.id = s.semester_id
    LEFT JOIN timetable_academicyear AS ay
      ON ay.id = sem.academic_year_id
    WHERE LOWER(gv.code) IN ('a', 'b', 'c', 'd', 'e')
),
ranked AS (
    SELECT
        fg.*,
        ROW_NUMBER() OVER (
            PARTITION BY fg.student_id, fg.course_id, fg.grade_code
            ORDER BY
                fg.semester_start_date ASC NULLS LAST,
                fg.semester_number ASC NULLS LAST,
                fg.section_default_score ASC,
                fg.section_number ASC,
                fg.id ASC
        ) AS rn
    FROM final_grades AS fg
),
keepers AS (
    SELECT
        student_id,
        course_id,
        grade_code,
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
        r.grade_code,
        r.section_id AS drop_section_id
    FROM ranked AS r
    JOIN keepers AS k
      ON k.student_id = r.student_id
     AND k.course_id = r.course_id
     AND k.grade_code = r.grade_code
    WHERE r.rn > 1
)
SELECT *
FROM to_drop;

SELECT
    COUNT(*) AS grades_to_delete,
    COUNT(DISTINCT (student_id, course_id, grade_code)) AS impacted_duplicate_groups
FROM tmp_grade_identical_final_dedup_plan;

-- 3) Apply or dry-run.
\if :apply
DELETE FROM registry_grade AS g
USING tmp_grade_identical_final_dedup_plan AS p
WHERE g.id = p.drop_grade_id;

SELECT
    'APPLY MODE: identical final-grade duplicates deleted.' AS status,
    COUNT(*) AS deleted_rows
FROM tmp_grade_identical_final_dedup_plan;
\else
SELECT
    'DRY-RUN MODE: no rows deleted. Re-run with -v apply=1 to apply.' AS status,
    COUNT(*) AS planned_delete_rows
FROM tmp_grade_identical_final_dedup_plan;
\endif

COMMIT;
