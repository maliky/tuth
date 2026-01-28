-- Default semester dates based on academic year rules.
-- Targets the default Django table name for app.timetable.models.Semester.

WITH year_parts AS (
    SELECT
        sem.id,
        sem.academic_year_id,
        sem.number,
        ay.start_date AS ay_start,
        COALESCE(
            ay.end_date,
            ay.start_date + INTERVAL '1 year' - INTERVAL '1 day'
        ) AS ay_end,
        EXTRACT(YEAR FROM ay.start_date)::int AS start_year,
        EXTRACT(YEAR FROM ay.start_date)::int + 1 AS end_year
    FROM timetable_semester AS sem
    JOIN timetable_academicyear AS ay
        ON ay.id = sem.academic_year_id
),
semester_dates AS (
    SELECT
        id,
        academic_year_id,
        number,
        ay_start,
        ay_end,
        CASE
            WHEN number = 0 THEN ay_start
            WHEN number = 1 THEN ay_start
            WHEN number = 2 THEN make_date(end_year, 1, 1)
            WHEN number = 3 THEN make_date(end_year, 6, 1)
            ELSE ay_start
        END AS start_date
    FROM year_parts
),
ordered_semesters AS (
    SELECT
        id,
        academic_year_id,
        number,
        ay_end,
        start_date,
        LEAD(start_date)
            OVER (PARTITION BY academic_year_id ORDER BY number) AS next_start_date
    FROM semester_dates
)
UPDATE timetable_semester AS sem
SET start_date = ordered_semesters.start_date,
    end_date = CASE
        WHEN ordered_semesters.number = 0 THEN ordered_semesters.ay_end
        WHEN ordered_semesters.next_start_date IS NOT NULL
            THEN ordered_semesters.next_start_date - INTERVAL '1 day'
        ELSE ordered_semesters.ay_end
    END
FROM ordered_semesters
WHERE sem.id = ordered_semesters.id;
