-- Pre-merge conflict checks for hard student merges.
-- Usage (psql/dbshell):
--   \set source_id 1
--   \set target_id 2
--   \i scripts/student_merge_conflicts.sql

-- Confirm the selected students.
SELECT
    s.id,
    s.student_id,
    s.long_name,
    pe.curriculum_id AS primary_curriculum_id,
    s.entry_semester_id,
    s.last_enrolled_semester_id,
    s.user_id
FROM people_student AS s
LEFT JOIN LATERAL (
    SELECT e.curriculum_id
    FROM people_stdcurrienroll AS e
    WHERE e.student_id = s.id
      AND e.is_primary = TRUE
    ORDER BY e.updated_at DESC, e.id DESC
    LIMIT 1
) AS pe ON TRUE
WHERE s.id IN (:source_id, :target_id)
ORDER BY s.id;

-- Related record counts per student.
SELECT student_id, COUNT(*) AS registration_count
FROM registry_registration
WHERE student_id IN (:source_id, :target_id)
GROUP BY student_id
ORDER BY student_id;

SELECT student_id, COUNT(*) AS grade_count
FROM registry_grade
WHERE student_id IN (:source_id, :target_id)
GROUP BY student_id
ORDER BY student_id;

SELECT student_id, COUNT(*) AS invoice_count
FROM finance_courseinvoice
WHERE student_id IN (:source_id, :target_id)
GROUP BY student_id
ORDER BY student_id;

SELECT student_id, COUNT(*) AS scholarship_count
FROM finance_scholarship
WHERE student_id IN (:source_id, :target_id)
GROUP BY student_id
ORDER BY student_id;

SELECT student_id, COUNT(*) AS snapshot_count
FROM finance_scholarshiptermsnapshot
WHERE student_id IN (:source_id, :target_id)
GROUP BY student_id
ORDER BY student_id;

SELECT person_id AS student_id, COUNT(*) AS document_count
FROM registry_docstd
WHERE person_id IN (:source_id, :target_id)
GROUP BY person_id
ORDER BY person_id;

-- Registration collisions on the same section.
SELECT
    s.section_id,
    s.id AS source_registration_id,
    t.id AS target_registration_id
FROM registry_registration AS s
JOIN registry_registration AS t
  ON t.section_id = s.section_id
WHERE s.student_id = :source_id
  AND t.student_id = :target_id
ORDER BY s.section_id;

-- Grade collisions on the same section.
SELECT
    s.section_id,
    s.id AS source_grade_id,
    t.id AS target_grade_id
FROM registry_grade AS s
JOIN registry_grade AS t
  ON t.section_id = s.section_id
WHERE s.student_id = :source_id
  AND t.student_id = :target_id
ORDER BY s.section_id;

-- Invoice collisions on the same curriculum course and semester.
SELECT
    s.curriculum_course_id,
    s.semester_id,
    s.id AS source_invoice_id,
    t.id AS target_invoice_id
FROM finance_courseinvoice AS s
JOIN finance_courseinvoice AS t
  ON t.curriculum_course_id = s.curriculum_course_id
 AND t.semester_id = s.semester_id
WHERE s.student_id = :source_id
  AND t.student_id = :target_id
ORDER BY s.curriculum_course_id, s.semester_id;

-- Scholarship snapshot collisions on the same semester.
SELECT
    s.semester_id,
    s.id AS source_snapshot_id,
    t.id AS target_snapshot_id
FROM finance_scholarshiptermsnapshot AS s
JOIN finance_scholarshiptermsnapshot AS t
  ON t.semester_id = s.semester_id
WHERE s.student_id = :source_id
  AND t.student_id = :target_id
ORDER BY s.semester_id;

-- Scholarship overlaps by donor.
SELECT
    s.donor_id,
    s.id AS source_scholarship_id,
    t.id AS target_scholarship_id
FROM finance_scholarship AS s
JOIN finance_scholarship AS t
  ON t.donor_id = s.donor_id
WHERE s.student_id = :source_id
  AND t.student_id = :target_id
ORDER BY s.donor_id;
