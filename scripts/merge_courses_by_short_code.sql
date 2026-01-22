-- Merge courses that share the same short_code.
-- Target selection: prefer course with description, else smallest id.
-- This script updates curriculum courses, sections, and prerequisites, then deletes duplicates.

BEGIN;

CREATE TEMP TABLE tmp_course_merge AS
WITH duplicates AS (
    SELECT
        short_code,
        MIN(id) FILTER (
            WHERE description IS NOT NULL AND btrim(description) <> ''
        ) AS preferred_with_desc,
        MIN(id) AS min_id,
        COUNT(*) AS total
    FROM academics_course
    WHERE short_code IS NOT NULL AND btrim(short_code) <> ''
    GROUP BY short_code
    HAVING COUNT(*) > 1
)
SELECT
    c.id AS source_id,
    -- > what does COALESCE means ?
    COALESCE(d.preferred_with_desc, d.min_id) AS target_id
FROM academics_course c
JOIN duplicates d ON c.short_code = d.short_code
WHERE c.id <> COALESCE(d.preferred_with_desc, d.min_id);

-- Remove prerequisites that would become self-referential.
DELETE FROM academics_prerequisite p
USING tmp_course_merge m
WHERE p.course_id = m.source_id
  AND p.prerequisite_course_id = m.target_id;

DELETE FROM academics_prerequisite p
USING tmp_course_merge m
WHERE p.prerequisite_course_id = m.source_id
  AND p.course_id = m.target_id;

-- Update prerequisite references to target courses.
UPDATE academics_prerequisite p
SET course_id = m.target_id
FROM tmp_course_merge m
WHERE p.course_id = m.source_id;

UPDATE academics_prerequisite p
SET prerequisite_course_id = m.target_id
FROM tmp_course_merge m
WHERE p.prerequisite_course_id = m.source_id;

-- Clean up self and duplicate prerequisite rows.
DELETE FROM academics_prerequisite
WHERE course_id = prerequisite_course_id;

DELETE FROM academics_prerequisite p
USING academics_prerequisite p2
WHERE p.id > p2.id
  AND p.course_id = p2.course_id
  AND p.prerequisite_course_id = p2.prerequisite_course_id
  AND p.curriculum_id IS NOT DISTINCT FROM p2.curriculum_id;

-- Merge curriculum course rows that would collide after course updates.
-- Materialize the pairs once so we can reuse them across statements.
CREATE TEMP TABLE tmp_cc_pairs AS
SELECT
    src.id AS src_id,
    tgt.id AS tgt_id
FROM academics_curriculumcourse src
JOIN tmp_course_merge m ON src.course_id = m.source_id
JOIN academics_curriculumcourse tgt
  ON tgt.curriculum_id = src.curriculum_id
 AND tgt.course_id = m.target_id;

UPDATE timetable_section s
SET curriculum_course_id = tmp_cc_pairs.tgt_id
FROM tmp_cc_pairs
WHERE s.curriculum_course_id = tmp_cc_pairs.src_id;

DELETE FROM academics_curriculumcourse cc
USING tmp_cc_pairs
WHERE cc.id = tmp_cc_pairs.src_id;

-- Update remaining curriculum courses to the target course.
UPDATE academics_curriculumcourse cc
SET course_id = m.target_id
FROM tmp_course_merge m
WHERE cc.course_id = m.source_id;

-- Remove any remaining duplicate curriculum course rows.
-- Persist the duplicate map for reuse across update/delete statements.
CREATE TEMP TABLE tmp_cc_dupes AS
SELECT
    cc.id AS drop_id,
    cc2.id AS keep_id
FROM academics_curriculumcourse cc
JOIN academics_curriculumcourse cc2
  ON cc.curriculum_id = cc2.curriculum_id
 AND cc.course_id = cc2.course_id
 AND cc.id > cc2.id;

UPDATE timetable_section s
SET curriculum_course_id = tmp_cc_dupes.keep_id
FROM tmp_cc_dupes
WHERE s.curriculum_course_id = tmp_cc_dupes.drop_id;

DELETE FROM academics_curriculumcourse cc
USING tmp_cc_dupes
WHERE cc.id = tmp_cc_dupes.drop_id;

-- Delete duplicate course rows.
DELETE FROM academics_course c
USING tmp_course_merge m
WHERE c.id = m.source_id;

DROP TABLE tmp_course_merge;
DROP TABLE tmp_cc_pairs;
DROP TABLE tmp_cc_dupes;

COMMIT;
