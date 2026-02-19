-- Normalize curriculum course level_number for a given course short_code.
-- Behavior:
-- - If exactly one defined level_number (non-null, not 99) exists across curricula,
--   set that level_number on all other rows for this course where level_number is null/99.
-- - If none or multiple defined level_number values exist, do nothing.
-- Usage (psql/dbshell):
--   \set course_short_code 'ACCT-201'
--   \i scripts/normalize_curriculumcourse_level_by_course.sql

-- Show the current distinct level numbers for the course.
WITH levels AS (
    SELECT DISTINCT cc.level_number
    FROM academics_curricrs AS cc
    JOIN academics_course AS c ON c.id = cc.course_id
    WHERE c.short_code = :'course_short_code'
      AND cc.level_number IS NOT NULL
      AND cc.level_number <> 99
)
SELECT
    COUNT(*) AS level_count,
    ARRAY_AGG(level_number ORDER BY level_number) AS level_numbers
FROM levels;

-- Update only when a single defined level exists.
WITH levels AS (
    SELECT COUNT(*) AS level_count, MIN(level_number) AS level_value
    FROM (
        SELECT DISTINCT cc.level_number
        FROM academics_curricrs AS cc
        JOIN academics_course AS c ON c.id = cc.course_id
        WHERE c.short_code = :'course_short_code'
          AND cc.level_number IS NOT NULL
          AND cc.level_number <> 99
    ) AS levels
)
UPDATE academics_curricrs AS cc
SET level_number = levels.level_value,
    year_number = CASE
        WHEN levels.level_value BETWEEN 1 AND 8
            THEN ((levels.level_value - 1) / 2 + 1)
        WHEN levels.level_value = 0
            THEN 99
        ELSE cc.year_number
    END,
    semester_number = CASE
        WHEN levels.level_value BETWEEN 1 AND 8
            THEN CASE WHEN levels.level_value % 2 = 1 THEN 1 ELSE 2 END
        WHEN levels.level_value = 0
            THEN 0
        ELSE cc.semester_number
    END
FROM levels, academics_course AS c
WHERE c.short_code = :'course_short_code'
  AND c.id = cc.course_id
  AND levels.level_count = 1
  AND (cc.level_number IS NULL OR cc.level_number = 99);
