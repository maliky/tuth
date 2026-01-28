-- Pre-merge conflict checks for hard department merges.
-- Usage (psql/dbshell):
--   \set source_id 1
--   \set target_id 2
--   \i scripts/department_merge_conflicts.sql

-- Confirm the selected departments.
SELECT id, code, shortname, long_name, college_id
FROM academics_department
WHERE id IN (:source_id, :target_id)
ORDER BY id;

-- Course counts per department.
SELECT
    department_id,
    COUNT(*) AS course_count
FROM academics_course
WHERE department_id IN (:source_id, :target_id)
GROUP BY department_id
ORDER BY department_id;

-- Courses that would collide on course number after a merge.
SELECT
    sc.id AS source_course_id,
    tc.id AS target_course_id,
    sc.number AS course_number,
    sc.short_code AS source_short_code,
    tc.short_code AS target_short_code,
    sc.title AS source_title,
    tc.title AS target_title
FROM academics_course AS sc
JOIN academics_course AS tc
  ON tc.department_id = :target_id
 AND sc.department_id = :source_id
 AND tc.number = sc.number
ORDER BY sc.number, sc.id;

-- Staff profiles currently tied to the source department.
SELECT
    id AS staff_id,
    staff_id AS staff_code,
    long_name,
    user_id
FROM people_staff
WHERE department_id = :source_id
ORDER BY staff_id;

-- Faculty linked to staff profiles in the source department.
SELECT
    f.id AS faculty_id,
    s.staff_id AS staff_code,
    s.long_name
FROM people_faculty AS f
JOIN people_staff AS s ON s.id = f.staff_profile_id
WHERE s.department_id = :source_id
ORDER BY s.staff_id;

-- Role assignments scoped to the source department.
SELECT
    id AS role_assignment_id,
    user_id,
    group_id,
    start_date,
    end_date
FROM people_roleassignment
WHERE department_id = :source_id
ORDER BY start_date, role_assignment_id;
