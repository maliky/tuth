-- One-time repair:
-- Ensure curriculum courses flagged as "other/undefined" are grouped in the
-- dedicated bucket used by admin inline grouping.
--
-- Target rows:
--   level_number IS NULL, 99 (undefined), or <= 0 (legacy/remedial bucket)
-- Desired bucket:
--   year_number = 99
--   semester_number = 0
--
-- Safe to re-run: the update only touches mismatched rows.

BEGIN;

-- Preview rows that will be normalized.
SELECT
    id,
    curriculum_id,
    course_id,
    level_number,
    year_number,
    semester_number
FROM academics_curriculumcourse
WHERE
    (level_number IS NULL OR level_number = 99 OR level_number <= 0)
    AND (
        COALESCE(year_number, -1) <> 99
        OR COALESCE(semester_number, -1) <> 0
    )
ORDER BY curriculum_id, course_id, id;

-- Apply normalization to the "other/undefined" bucket.
UPDATE academics_curriculumcourse
SET
    year_number = 99,
    semester_number = 0
WHERE
    (level_number IS NULL OR level_number = 99 OR level_number <= 0)
    AND (
        COALESCE(year_number, -1) <> 99
        OR COALESCE(semester_number, -1) <> 0
    );

-- Summary after update.
SELECT
    COUNT(*) AS rows_now_in_other_grouping
FROM academics_curriculumcourse
WHERE
    (level_number IS NULL OR level_number = 99 OR level_number <= 0)
    AND year_number = 99
    AND semester_number = 0;

COMMIT;
