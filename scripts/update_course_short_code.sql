-- Normalize course short_code by removing the first hyphen before the number block.
UPDATE academics_course
SET short_code = regexp_replace(short_code, '^([A-Za-z]+)-([0-9].*)$', '\1\2')
WHERE short_code ~ '^[A-Za-z]+-[0-9]';

-- Normalize course code by removing the first hyphen before the number block.
UPDATE academics_course
SET code = regexp_replace(code, '^([A-Za-z]+)-([0-9].*)$', '\1\2')
WHERE code ~ '^[A-Za-z]+-[0-9]';

-- Repair accidental literal backreference tokens from prior runs.
UPDATE academics_course AS course
SET short_code = upper(dept.code || course.number)
FROM academics_department AS dept
WHERE course.department_id = dept.id
  AND course.short_code = '\1\2';

UPDATE academics_course AS course
SET code = upper(dept.shortname || course.number)
FROM academics_department AS dept
WHERE course.department_id = dept.id
  AND course.code = '\1\2';
