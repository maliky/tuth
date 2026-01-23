-- Default semester dates based on academic year rules.
-- Targets the default Django table name for app.timetable.models.Semester.

WITH year_parts AS (
    SELECT
        sem.id,
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
)
UPDATE timetable_semester AS sem
SET start_date = CASE
        WHEN year_parts.number = 0 THEN year_parts.ay_start
        WHEN year_parts.number = 1 THEN year_parts.ay_start
        WHEN year_parts.number = 2 THEN make_date(year_parts.end_year, 1, 1)
        WHEN year_parts.number = 3 THEN make_date(year_parts.end_year, 6, 1)
        ELSE year_parts.ay_start
    END,
    end_date = CASE
        WHEN year_parts.number = 0 THEN year_parts.ay_end
        WHEN year_parts.number = 1 THEN make_date(year_parts.start_year, 12, 31)
        WHEN year_parts.number = 2 THEN make_date(year_parts.end_year, 5, 31)
        WHEN year_parts.number = 3 THEN year_parts.ay_end
        ELSE year_parts.ay_end
    END
FROM year_parts
WHERE sem.id = year_parts.id;
