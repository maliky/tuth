-- Curriculum merge with preflight classification, optional apply, and persistent audit logs.
--
-- Purpose:
--   1) Preflight: classify source rows with explicit reason codes.
--   2) Apply   : perform merge updates when apply=1.
--   3) Report  : summarize all outcomes from audit logs.
--
-- This script is additive (new audit tables) and does not overlap existing
-- precheck-only scripts such as curriculum_merge_conflicts.sql.
--
-- Usage (dry-run/preflight only):
--   cat scripts/curriculum_merge_with_audit.sql | docker-compose -f docker-compose-preprod.yml exec -T db \
--     psql -U "$POSTGRES_USER" -d "$POSTGRES_DB" -v source_id=206 -v target_id=31 -v apply=0 -v run_label='curri_206_to_31_dry'
--
-- Usage (apply with logs):
--   cat scripts/curriculum_merge_with_audit.sql | docker-compose -f docker-compose-preprod.yml exec -T db \
--     psql -U "$POSTGRES_USER" -d "$POSTGRES_DB" -v source_id=206 -v target_id=31 -v apply=1 -v run_label='curri_206_to_31_apply'

\set ON_ERROR_STOP on

\if :{?source_id}
\else
\set source_id 0
\endif

\if :{?target_id}
\else
\set target_id 0
\endif

\if :{?apply}
\else
\set apply 0
\endif

\if :{?run_label}
\else
\set run_label 'curriculum_merge_manual'
\endif

CREATE TABLE IF NOT EXISTS scripts_curriculum_merge_run (
    run_id BIGSERIAL PRIMARY KEY,
    run_label TEXT NOT NULL,
    source_curriculum_id BIGINT NOT NULL,
    target_curriculum_id BIGINT NOT NULL,
    apply_mode BOOLEAN NOT NULL DEFAULT FALSE,
    started_at TIMESTAMPTZ NOT NULL DEFAULT NOW(),
    finished_at TIMESTAMPTZ,
    status TEXT NOT NULL DEFAULT 'running',
    note TEXT
);

CREATE TABLE IF NOT EXISTS scripts_curriculum_merge_log (
    log_id BIGSERIAL PRIMARY KEY,
    run_id BIGINT NOT NULL REFERENCES scripts_curriculum_merge_run(run_id) ON DELETE CASCADE,
    stage TEXT NOT NULL,
    entity TEXT NOT NULL,
    source_id BIGINT,
    target_id BIGINT,
    section_id BIGINT,
    student_id BIGINT,
    reason_code TEXT NOT NULL,
    detail JSONB NOT NULL DEFAULT '{}'::JSONB,
    created_at TIMESTAMPTZ NOT NULL DEFAULT NOW()
);

CREATE INDEX IF NOT EXISTS idx_scripts_curriculum_merge_log_run_id
    ON scripts_curriculum_merge_log (run_id);

CREATE INDEX IF NOT EXISTS idx_scripts_curriculum_merge_log_reason
    ON scripts_curriculum_merge_log (reason_code);

INSERT INTO scripts_curriculum_merge_run (
    run_label,
    source_curriculum_id,
    target_curriculum_id,
    apply_mode,
    status
)
VALUES (
    :'run_label',
    :source_id,
    :target_id,
    (:apply::INT = 1),
    'running'
)
RETURNING run_id
\gset

SELECT set_config('app.curriculum_merge.run_id', :'run_id', FALSE);
SELECT set_config('app.curriculum_merge.source_id', :'source_id', FALSE);
SELECT set_config('app.curriculum_merge.target_id', :'target_id', FALSE);
SELECT set_config('app.curriculum_merge.apply', :'apply', FALSE);

DO $$
DECLARE
    v_run_id BIGINT := current_setting('app.curriculum_merge.run_id')::BIGINT;
    v_source BIGINT := current_setting('app.curriculum_merge.source_id')::BIGINT;
    v_target BIGINT := current_setting('app.curriculum_merge.target_id')::BIGINT;
    v_apply BOOLEAN := (current_setting('app.curriculum_merge.apply')::INT = 1);
    v_rows INT := 0;
    v_row RECORD;
    v_sec RECORD;
BEGIN
    IF v_source <= 0 OR v_target <= 0 THEN
        RAISE EXCEPTION 'source_id and target_id must be positive. got source_id=%, target_id=%', v_source, v_target;
    END IF;

    IF v_source = v_target THEN
        RAISE EXCEPTION 'source_id and target_id must differ. both=%', v_source;
    END IF;

    IF NOT EXISTS (SELECT 1 FROM academics_curriculum WHERE id = v_source) THEN
        RAISE EXCEPTION 'source curriculum % does not exist', v_source;
    END IF;

    IF NOT EXISTS (SELECT 1 FROM academics_curriculum WHERE id = v_target) THEN
        RAISE EXCEPTION 'target curriculum % does not exist', v_target;
    END IF;

    CREATE TEMP TABLE tmp_curricourse_pairs (
        source_cc_id BIGINT PRIMARY KEY,
        source_course_id BIGINT NOT NULL,
        source_department_id BIGINT,
        source_course_number TEXT,
        identity_key TEXT,
        target_cc_id BIGINT,
        has_invoice BOOLEAN NOT NULL DEFAULT FALSE
    ) ON COMMIT DROP;

    CREATE TEMP TABLE tmp_enrollment_pairs (
        source_enroll_id BIGINT PRIMARY KEY,
        target_enroll_id BIGINT,
        student_id BIGINT NOT NULL,
        source_entry_semester_id BIGINT,
        target_entry_semester_id BIGINT,
        blocked_by_entry_semester BOOLEAN NOT NULL DEFAULT FALSE
    ) ON COMMIT DROP;

    WITH src AS (
        SELECT
            scc.id AS source_cc_id,
            scc.course_id AS source_course_id,
            sc.department_id AS source_department_id,
            BTRIM(sc.number) AS source_course_number,
            CONCAT(sc.department_id, ':', BTRIM(sc.number)) AS identity_key
        FROM academics_curricrs AS scc
        JOIN academics_course AS sc ON sc.id = scc.course_id
        WHERE scc.curriculum_id = v_source
    ),
    tgt_ranked AS (
        SELECT
            tcc.id AS target_cc_id,
            tc.department_id,
            BTRIM(tc.number) AS course_number,
            ROW_NUMBER() OVER (
                PARTITION BY tc.department_id, BTRIM(tc.number)
                ORDER BY tcc.id
            ) AS rn
        FROM academics_curricrs AS tcc
        JOIN academics_course AS tc ON tc.id = tcc.course_id
        WHERE tcc.curriculum_id = v_target
    )
    INSERT INTO tmp_curricourse_pairs (
        source_cc_id,
        source_course_id,
        source_department_id,
        source_course_number,
        identity_key,
        target_cc_id
    )
    SELECT
        src.source_cc_id,
        src.source_course_id,
        src.source_department_id,
        src.source_course_number,
        src.identity_key,
        tgt_ranked.target_cc_id
    FROM src
    LEFT JOIN tgt_ranked
      ON tgt_ranked.department_id = src.source_department_id
     AND tgt_ranked.course_number = src.source_course_number
     AND tgt_ranked.rn = 1;

    UPDATE tmp_curricourse_pairs AS p
    SET has_invoice = EXISTS (
        SELECT 1
        FROM finance_courseinvoice AS ci
        WHERE ci.curriculum_course_id = p.source_cc_id
    );

    INSERT INTO scripts_curriculum_merge_log (
        run_id, stage, entity, source_id, target_id, reason_code, detail
    )
    SELECT
        v_run_id,
        'preflight',
        'curricourse',
        p.source_cc_id,
        p.target_cc_id,
        CASE
            WHEN p.target_cc_id IS NULL THEN 'CURRICOURSE_NO_TARGET'
            ELSE 'CURRICOURSE_TARGET_MATCH'
        END,
        JSONB_BUILD_OBJECT(
            'source_course_id', p.source_course_id,
            'identity_key', p.identity_key,
            'has_invoice', p.has_invoice
        )
    FROM tmp_curricourse_pairs AS p;

    INSERT INTO scripts_curriculum_merge_log (
        run_id, stage, entity, source_id, target_id, reason_code, detail
    )
    SELECT
        v_run_id,
        'preflight',
        'curricourse',
        p.source_cc_id,
        p.target_cc_id,
        'CURRICOURSE_INVOICE_BLOCK',
        JSONB_BUILD_OBJECT(
            'source_course_id', p.source_course_id,
            'identity_key', p.identity_key
        )
    FROM tmp_curricourse_pairs AS p
    WHERE p.target_cc_id IS NOT NULL
      AND p.has_invoice = TRUE;

    INSERT INTO tmp_enrollment_pairs (
        source_enroll_id,
        target_enroll_id,
        student_id,
        source_entry_semester_id,
        target_entry_semester_id,
        blocked_by_entry_semester
    )
    SELECT
        src.id AS source_enroll_id,
        tgt.id AS target_enroll_id,
        src.student_id,
        src.entry_semester_id,
        tgt.entry_semester_id,
        (
            src.entry_semester_id IS NOT NULL
            AND tgt.entry_semester_id IS NOT NULL
            AND src.entry_semester_id <> tgt.entry_semester_id
        ) AS blocked_by_entry_semester
    FROM people_stdcurrienroll src
    LEFT JOIN people_stdcurrienroll tgt
      ON tgt.student_id = src.student_id
     AND tgt.curriculum_id = v_target
    WHERE src.curriculum_id = v_source;

    INSERT INTO scripts_curriculum_merge_log (
        run_id, stage, entity, source_id, target_id, student_id, reason_code, detail
    )
    SELECT
        v_run_id,
        'preflight',
        'enrollment',
        e.source_enroll_id,
        e.target_enroll_id,
        e.student_id,
        CASE
            WHEN e.target_enroll_id IS NULL THEN 'ENROLLMENT_MOVE_READY'
            WHEN e.blocked_by_entry_semester THEN 'ENROLLMENT_BLOCK_ENTRY_SEMESTER'
            ELSE 'ENROLLMENT_MERGE_READY'
        END,
        JSONB_BUILD_OBJECT(
            'source_entry_semester_id', e.source_entry_semester_id,
            'target_entry_semester_id', e.target_entry_semester_id
        )
    FROM tmp_enrollment_pairs e;

    CREATE TEMP TABLE tmp_section_candidates (
        source_section_id BIGINT PRIMARY KEY,
        source_cc_id BIGINT NOT NULL,
        target_cc_id BIGINT,
        semester_id BIGINT NOT NULL,
        source_number INT NOT NULL,
        candidate_section_id BIGINT,
        candidate_type TEXT,
        overlap_diff INT NOT NULL DEFAULT 0,
        overlap_same INT NOT NULL DEFAULT 0,
        source_grade_count INT NOT NULL DEFAULT 0,
        source_registration_count INT NOT NULL DEFAULT 0
    ) ON COMMIT DROP;

    WITH src_sections AS (
        SELECT
            s.id AS source_section_id,
            s.curriculum_course_id AS source_cc_id,
            p.target_cc_id,
            s.semester_id,
            s.number AS source_number
        FROM timetable_section AS s
        JOIN tmp_curricourse_pairs AS p ON p.source_cc_id = s.curriculum_course_id
        WHERE p.target_cc_id IS NOT NULL
    ),
    same_number AS (
        SELECT
            src.source_section_id,
            MIN(t.id) AS target_section_id
        FROM src_sections AS src
        JOIN timetable_section AS t
          ON t.curriculum_course_id = src.target_cc_id
         AND t.semester_id = src.semester_id
         AND t.number = src.source_number
        GROUP BY src.source_section_id
    ),
    target_semester_counts AS (
        SELECT
            src.source_section_id,
            COUNT(t.id) AS target_section_count,
            MIN(t.id) AS singleton_target_section_id
        FROM src_sections AS src
        LEFT JOIN timetable_section AS t
          ON t.curriculum_course_id = src.target_cc_id
         AND t.semester_id = src.semester_id
        GROUP BY src.source_section_id
    )
    INSERT INTO tmp_section_candidates (
        source_section_id,
        source_cc_id,
        target_cc_id,
        semester_id,
        source_number,
        candidate_section_id,
        candidate_type
    )
    SELECT
        src.source_section_id,
        src.source_cc_id,
        src.target_cc_id,
        src.semester_id,
        src.source_number,
        COALESCE(sn.target_section_id,
            CASE
                WHEN tsc.target_section_count = 1 THEN tsc.singleton_target_section_id
                ELSE NULL
            END
        ) AS candidate_section_id,
        CASE
            WHEN sn.target_section_id IS NOT NULL THEN 'same_number'
            WHEN tsc.target_section_count = 1 THEN 'singleton_semester'
            ELSE 'none'
        END AS candidate_type
    FROM src_sections AS src
    LEFT JOIN same_number AS sn ON sn.source_section_id = src.source_section_id
    LEFT JOIN target_semester_counts AS tsc ON tsc.source_section_id = src.source_section_id;

    UPDATE tmp_section_candidates AS c
    SET
        source_grade_count = stats.source_grade_count,
        source_registration_count = stats.source_registration_count,
        overlap_diff = stats.overlap_diff,
        overlap_same = stats.overlap_same
    FROM (
        SELECT
            c2.source_section_id,
            COALESCE((SELECT COUNT(*) FROM registry_grade g WHERE g.section_id = c2.source_section_id), 0) AS source_grade_count,
            COALESCE((SELECT COUNT(*) FROM registry_registration r WHERE r.section_id = c2.source_section_id), 0) AS source_registration_count,
            COALESCE((
                SELECT COUNT(*)
                FROM registry_grade gs
                JOIN registry_grade gt
                  ON gt.section_id = c2.candidate_section_id
                 AND gt.student_id = gs.student_id
                WHERE gs.section_id = c2.source_section_id
                  AND gs.value_id IS DISTINCT FROM gt.value_id
            ), 0) AS overlap_diff,
            COALESCE((
                SELECT COUNT(*)
                FROM registry_grade gs
                JOIN registry_grade gt
                  ON gt.section_id = c2.candidate_section_id
                 AND gt.student_id = gs.student_id
                WHERE gs.section_id = c2.source_section_id
                  AND gs.value_id IS NOT DISTINCT FROM gt.value_id
            ), 0) AS overlap_same
        FROM tmp_section_candidates c2
    ) AS stats
    WHERE stats.source_section_id = c.source_section_id;

    INSERT INTO scripts_curriculum_merge_log (
        run_id, stage, entity, source_id, target_id, section_id, reason_code, detail
    )
    SELECT
        v_run_id,
        'preflight',
        'section',
        c.source_cc_id,
        c.target_cc_id,
        c.source_section_id,
        CASE
            WHEN c.candidate_section_id IS NULL THEN 'SECTION_REPARENT_READY'
            WHEN c.overlap_diff > 0 THEN 'SECTION_GRADE_VALUE_CONFLICT'
            WHEN c.overlap_same > 0 THEN 'SECTION_DUPLICATE_STUDENT_GRADE'
            ELSE 'SECTION_MERGE_READY'
        END,
        JSONB_BUILD_OBJECT(
            'semester_id', c.semester_id,
            'source_number', c.source_number,
            'candidate_section_id', c.candidate_section_id,
            'candidate_type', c.candidate_type,
            'source_grade_count', c.source_grade_count,
            'source_registration_count', c.source_registration_count,
            'overlap_same', c.overlap_same,
            'overlap_diff', c.overlap_diff
        )
    FROM tmp_section_candidates c;

    IF v_apply THEN
        -- Move enrollment rows without an existing target enrollment row.
        WITH moved AS (
            UPDATE people_stdcurrienroll s
            SET curriculum_id = v_target
            FROM tmp_enrollment_pairs e
            WHERE s.id = e.source_enroll_id
              AND e.target_enroll_id IS NULL
            RETURNING s.id AS source_enroll_id, s.student_id
        )
        INSERT INTO scripts_curriculum_merge_log (
            run_id, stage, entity, source_id, target_id, student_id, reason_code
        )
        SELECT
            v_run_id,
            'apply',
            'enrollment',
            moved.source_enroll_id,
            v_target,
            moved.student_id,
            'ENROLLMENT_MOVED_TO_TARGET'
        FROM moved;

        -- Merge overlapping enrollment rows when entry-semester rule allows it.
        WITH primary_transfer AS (
            SELECT e.student_id, e.target_enroll_id
            FROM tmp_enrollment_pairs e
            JOIN people_stdcurrienroll s ON s.id = e.source_enroll_id
            JOIN people_stdcurrienroll t ON t.id = e.target_enroll_id
            WHERE e.target_enroll_id IS NOT NULL
              AND e.blocked_by_entry_semester = FALSE
              AND s.is_primary = TRUE
              AND t.is_primary = FALSE
        ),
        normalized_primary_before_update AS (
            UPDATE people_stdcurrienroll other
            SET is_primary = FALSE
            FROM primary_transfer p
            WHERE other.student_id = p.student_id
              AND other.id <> p.target_enroll_id
              AND other.is_primary = TRUE
            RETURNING other.id
        )
        INSERT INTO scripts_curriculum_merge_log (
            run_id, stage, entity, reason_code, detail
        )
        SELECT
            v_run_id,
            'apply',
            'enrollment',
            'ENROLLMENT_PRIMARY_NORMALIZED_BEFORE_UPDATE',
            JSONB_BUILD_OBJECT('rows', COUNT(*))
        FROM normalized_primary_before_update;

        -- Merge overlapping enrollment rows when entry-semester rule allows it.
        WITH updated_targets AS (
            UPDATE people_stdcurrienroll t
            SET
                entry_semester_id = COALESCE(t.entry_semester_id, s.entry_semester_id),
                exit_semester_id = COALESCE(t.exit_semester_id, s.exit_semester_id),
                is_primary = (t.is_primary OR s.is_primary),
                is_active = (t.is_active OR s.is_active),
                creation_date = LEAST(t.creation_date, s.creation_date),
                updated_at = NOW()
            FROM tmp_enrollment_pairs e
            JOIN people_stdcurrienroll s ON s.id = e.source_enroll_id
            WHERE t.id = e.target_enroll_id
              AND e.target_enroll_id IS NOT NULL
              AND e.blocked_by_entry_semester = FALSE
            RETURNING t.id AS target_enroll_id, t.student_id, t.is_primary
        ),
        normalized_primary AS (
            UPDATE people_stdcurrienroll other
            SET is_primary = FALSE
            FROM updated_targets ut
            WHERE ut.is_primary = TRUE
              AND other.student_id = ut.student_id
              AND other.id <> ut.target_enroll_id
              AND other.is_primary = TRUE
            RETURNING other.id
        )
        INSERT INTO scripts_curriculum_merge_log (
            run_id, stage, entity, reason_code, detail
        )
        SELECT
            v_run_id,
            'apply',
            'enrollment',
            'ENROLLMENT_PRIMARY_NORMALIZED',
            JSONB_BUILD_OBJECT('rows', COUNT(*))
        FROM normalized_primary;

        WITH deleted_sources AS (
            DELETE FROM people_stdcurrienroll s
            USING tmp_enrollment_pairs e
            WHERE s.id = e.source_enroll_id
              AND e.target_enroll_id IS NOT NULL
              AND e.blocked_by_entry_semester = FALSE
            RETURNING s.id AS source_enroll_id, s.student_id
        )
        INSERT INTO scripts_curriculum_merge_log (
            run_id, stage, entity, source_id, target_id, student_id, reason_code
        )
        SELECT
            v_run_id,
            'apply',
            'enrollment',
            d.source_enroll_id,
            v_target,
            d.student_id,
            'ENROLLMENT_SOURCE_ROW_DELETED_AFTER_MERGE'
        FROM deleted_sources d;

        INSERT INTO scripts_curriculum_merge_log (
            run_id, stage, entity, source_id, target_id, student_id, reason_code, detail
        )
        SELECT
            v_run_id,
            'apply',
            'enrollment',
            e.source_enroll_id,
            e.target_enroll_id,
            e.student_id,
            'ENROLLMENT_SKIPPED_ENTRY_SEMESTER_BLOCK',
            JSONB_BUILD_OBJECT(
                'source_entry_semester_id', e.source_entry_semester_id,
                'target_entry_semester_id', e.target_entry_semester_id
            )
        FROM tmp_enrollment_pairs e
        WHERE e.target_enroll_id IS NOT NULL
          AND e.blocked_by_entry_semester = TRUE;

        UPDATE academics_major
        SET curriculum_id = v_target
        WHERE curriculum_id = v_source;
        GET DIAGNOSTICS v_rows = ROW_COUNT;
        INSERT INTO scripts_curriculum_merge_log (
            run_id, stage, entity, reason_code, detail
        ) VALUES (
            v_run_id,
            'apply',
            'summary',
            'MAJOR_ROWS_MOVED',
            JSONB_BUILD_OBJECT('rows', v_rows)
        );

        UPDATE academics_minor
        SET curriculum_id = v_target
        WHERE curriculum_id = v_source;
        GET DIAGNOSTICS v_rows = ROW_COUNT;
        INSERT INTO scripts_curriculum_merge_log (
            run_id, stage, entity, reason_code, detail
        ) VALUES (
            v_run_id,
            'apply',
            'summary',
            'MINOR_ROWS_MOVED',
            JSONB_BUILD_OBJECT('rows', v_rows)
        );

        FOR v_row IN
            SELECT id, course_id, prerequisite_course_id
            FROM academics_prerequisite
            WHERE curriculum_id = v_source
            ORDER BY id
        LOOP
            IF EXISTS (
                SELECT 1
                FROM academics_prerequisite p2
                WHERE p2.curriculum_id = v_target
                  AND p2.course_id = v_row.course_id
                  AND p2.prerequisite_course_id = v_row.prerequisite_course_id
            ) THEN
                DELETE FROM academics_prerequisite WHERE id = v_row.id;
                INSERT INTO scripts_curriculum_merge_log (
                    run_id, stage, entity, source_id, reason_code, detail
                ) VALUES (
                    v_run_id,
                    'apply',
                    'prerequisite',
                    v_row.id,
                    'PREREQUISITE_DUPLICATE_DROPPED',
                    JSONB_BUILD_OBJECT(
                        'course_id', v_row.course_id,
                        'prerequisite_course_id', v_row.prerequisite_course_id
                    )
                );
            ELSE
                UPDATE academics_prerequisite
                SET curriculum_id = v_target
                WHERE id = v_row.id;
                INSERT INTO scripts_curriculum_merge_log (
                    run_id, stage, entity, source_id, target_id, reason_code, detail
                ) VALUES (
                    v_run_id,
                    'apply',
                    'prerequisite',
                    v_row.id,
                    v_target,
                    'PREREQUISITE_MOVED',
                    JSONB_BUILD_OBJECT(
                        'course_id', v_row.course_id,
                        'prerequisite_course_id', v_row.prerequisite_course_id
                    )
                );
            END IF;
        END LOOP;

        FOR v_row IN
            SELECT *
            FROM tmp_curricourse_pairs
            ORDER BY source_cc_id
        LOOP
            IF v_row.target_cc_id IS NULL THEN
                UPDATE academics_curricrs
                SET curriculum_id = v_target
                WHERE id = v_row.source_cc_id;
                INSERT INTO scripts_curriculum_merge_log (
                    run_id, stage, entity, source_id, target_id, reason_code, detail
                ) VALUES (
                    v_run_id,
                    'apply',
                    'curricourse',
                    v_row.source_cc_id,
                    v_target,
                    'CURRICOURSE_MOVED_TO_TARGET',
                    JSONB_BUILD_OBJECT('identity_key', v_row.identity_key)
                );
                CONTINUE;
            END IF;

            IF v_row.has_invoice THEN
                INSERT INTO scripts_curriculum_merge_log (
                    run_id, stage, entity, source_id, target_id, reason_code, detail
                ) VALUES (
                    v_run_id,
                    'apply',
                    'curricourse',
                    v_row.source_cc_id,
                    v_row.target_cc_id,
                    'CURRICOURSE_SKIPPED_INVOICE',
                    JSONB_BUILD_OBJECT('identity_key', v_row.identity_key)
                );
                CONTINUE;
            END IF;

            FOR v_sec IN
                SELECT *
                FROM tmp_section_candidates
                WHERE source_cc_id = v_row.source_cc_id
                ORDER BY source_section_id
            LOOP
                IF v_sec.candidate_section_id IS NULL THEN
                    UPDATE timetable_section
                    SET curriculum_course_id = v_row.target_cc_id
                    WHERE id = v_sec.source_section_id;

                    INSERT INTO scripts_curriculum_merge_log (
                        run_id, stage, entity, source_id, target_id, section_id, reason_code, detail
                    ) VALUES (
                        v_run_id,
                        'apply',
                        'section',
                        v_row.source_cc_id,
                        v_row.target_cc_id,
                        v_sec.source_section_id,
                        'SECTION_REPARENTED_TO_TARGET_CURRICOURSE',
                        JSONB_BUILD_OBJECT(
                            'semester_id', v_sec.semester_id,
                            'source_number', v_sec.source_number
                        )
                    );
                    CONTINUE;
                END IF;

                IF v_sec.overlap_diff > 0 THEN
                    INSERT INTO scripts_curriculum_merge_log (
                        run_id, stage, entity, source_id, target_id, section_id, reason_code, detail
                    ) VALUES (
                        v_run_id,
                        'apply',
                        'section',
                        v_row.source_cc_id,
                        v_row.target_cc_id,
                        v_sec.source_section_id,
                        'SECTION_SKIPPED_GRADE_VALUE_CONFLICT',
                        JSONB_BUILD_OBJECT(
                            'candidate_section_id', v_sec.candidate_section_id,
                            'overlap_diff', v_sec.overlap_diff
                        )
                    );
                    CONTINUE;
                END IF;

                DELETE FROM registry_grade gs
                USING registry_grade gt
                WHERE gs.section_id = v_sec.source_section_id
                  AND gt.section_id = v_sec.candidate_section_id
                  AND gt.student_id = gs.student_id;
                GET DIAGNOSTICS v_rows = ROW_COUNT;
                IF v_rows > 0 THEN
                    INSERT INTO scripts_curriculum_merge_log (
                        run_id, stage, entity, source_id, target_id, section_id, reason_code, detail
                    ) VALUES (
                        v_run_id,
                        'apply',
                        'section',
                        v_row.source_cc_id,
                        v_row.target_cc_id,
                        v_sec.source_section_id,
                        'SECTION_DUPLICATE_GRADES_REMOVED',
                        JSONB_BUILD_OBJECT(
                            'candidate_section_id', v_sec.candidate_section_id,
                            'rows', v_rows
                        )
                    );
                END IF;

                UPDATE registry_grade gs
                SET section_id = v_sec.candidate_section_id
                WHERE gs.section_id = v_sec.source_section_id
                  AND NOT EXISTS (
                      SELECT 1
                      FROM registry_grade gt
                      WHERE gt.section_id = v_sec.candidate_section_id
                        AND gt.student_id = gs.student_id
                  );
                GET DIAGNOSTICS v_rows = ROW_COUNT;
                IF v_rows > 0 THEN
                    INSERT INTO scripts_curriculum_merge_log (
                        run_id, stage, entity, source_id, target_id, section_id, reason_code, detail
                    ) VALUES (
                        v_run_id,
                        'apply',
                        'section',
                        v_row.source_cc_id,
                        v_row.target_cc_id,
                        v_sec.source_section_id,
                        'SECTION_GRADES_MOVED',
                        JSONB_BUILD_OBJECT(
                            'candidate_section_id', v_sec.candidate_section_id,
                            'rows', v_rows
                        )
                    );
                END IF;

                DELETE FROM registry_registration rs
                USING registry_registration rt
                WHERE rs.section_id = v_sec.source_section_id
                  AND rt.section_id = v_sec.candidate_section_id
                  AND rt.student_id = rs.student_id;
                GET DIAGNOSTICS v_rows = ROW_COUNT;
                IF v_rows > 0 THEN
                    INSERT INTO scripts_curriculum_merge_log (
                        run_id, stage, entity, source_id, target_id, section_id, reason_code, detail
                    ) VALUES (
                        v_run_id,
                        'apply',
                        'section',
                        v_row.source_cc_id,
                        v_row.target_cc_id,
                        v_sec.source_section_id,
                        'SECTION_DUPLICATE_REGISTRATIONS_REMOVED',
                        JSONB_BUILD_OBJECT(
                            'candidate_section_id', v_sec.candidate_section_id,
                            'rows', v_rows
                        )
                    );
                END IF;

                UPDATE registry_registration rs
                SET section_id = v_sec.candidate_section_id
                WHERE rs.section_id = v_sec.source_section_id
                  AND NOT EXISTS (
                      SELECT 1
                      FROM registry_registration rt
                      WHERE rt.section_id = v_sec.candidate_section_id
                        AND rt.student_id = rs.student_id
                  );
                GET DIAGNOSTICS v_rows = ROW_COUNT;
                IF v_rows > 0 THEN
                    INSERT INTO scripts_curriculum_merge_log (
                        run_id, stage, entity, source_id, target_id, section_id, reason_code, detail
                    ) VALUES (
                        v_run_id,
                        'apply',
                        'section',
                        v_row.source_cc_id,
                        v_row.target_cc_id,
                        v_sec.source_section_id,
                        'SECTION_REGISTRATIONS_MOVED',
                        JSONB_BUILD_OBJECT(
                            'candidate_section_id', v_sec.candidate_section_id,
                            'rows', v_rows
                        )
                    );
                END IF;

                DELETE FROM timetable_secsession ss
                USING timetable_secsession st
                WHERE ss.section_id = v_sec.source_section_id
                  AND ss.schedule_id IS NOT NULL
                  AND st.section_id = v_sec.candidate_section_id
                  AND st.schedule_id = ss.schedule_id;
                GET DIAGNOSTICS v_rows = ROW_COUNT;
                IF v_rows > 0 THEN
                    INSERT INTO scripts_curriculum_merge_log (
                        run_id, stage, entity, source_id, target_id, section_id, reason_code, detail
                    ) VALUES (
                        v_run_id,
                        'apply',
                        'section',
                        v_row.source_cc_id,
                        v_row.target_cc_id,
                        v_sec.source_section_id,
                        'SECTION_DUPLICATE_SESSIONS_REMOVED',
                        JSONB_BUILD_OBJECT(
                            'candidate_section_id', v_sec.candidate_section_id,
                            'rows', v_rows
                        )
                    );
                END IF;

                UPDATE timetable_secsession ss
                SET section_id = v_sec.candidate_section_id
                WHERE ss.section_id = v_sec.source_section_id
                  AND (
                      ss.schedule_id IS NULL
                      OR NOT EXISTS (
                          SELECT 1
                          FROM timetable_secsession st
                          WHERE st.section_id = v_sec.candidate_section_id
                            AND st.schedule_id = ss.schedule_id
                      )
                  );
                GET DIAGNOSTICS v_rows = ROW_COUNT;
                IF v_rows > 0 THEN
                    INSERT INTO scripts_curriculum_merge_log (
                        run_id, stage, entity, source_id, target_id, section_id, reason_code, detail
                    ) VALUES (
                        v_run_id,
                        'apply',
                        'section',
                        v_row.source_cc_id,
                        v_row.target_cc_id,
                        v_sec.source_section_id,
                        'SECTION_SESSIONS_MOVED',
                        JSONB_BUILD_OBJECT(
                            'candidate_section_id', v_sec.candidate_section_id,
                            'rows', v_rows
                        )
                    );
                END IF;

                BEGIN
                    DELETE FROM timetable_section WHERE id = v_sec.source_section_id;
                    IF FOUND THEN
                        INSERT INTO scripts_curriculum_merge_log (
                            run_id, stage, entity, source_id, target_id, section_id, reason_code, detail
                        ) VALUES (
                            v_run_id,
                            'apply',
                            'section',
                            v_row.source_cc_id,
                            v_row.target_cc_id,
                            v_sec.source_section_id,
                            'SECTION_MERGED_AND_DELETED',
                            JSONB_BUILD_OBJECT('candidate_section_id', v_sec.candidate_section_id)
                        );
                    ELSE
                        INSERT INTO scripts_curriculum_merge_log (
                            run_id, stage, entity, source_id, target_id, section_id, reason_code
                        ) VALUES (
                            v_run_id,
                            'apply',
                            'section',
                            v_row.source_cc_id,
                            v_row.target_cc_id,
                            v_sec.source_section_id,
                            'SECTION_DELETE_NOOP'
                        );
                    END IF;
                EXCEPTION WHEN foreign_key_violation THEN
                    INSERT INTO scripts_curriculum_merge_log (
                        run_id, stage, entity, source_id, target_id, section_id, reason_code
                    ) VALUES (
                        v_run_id,
                        'apply',
                        'section',
                        v_row.source_cc_id,
                        v_row.target_cc_id,
                        v_sec.source_section_id,
                        'SECTION_DELETE_PROTECTED'
                    );
                END;
            END LOOP;

            BEGIN
                DELETE FROM academics_curricrs WHERE id = v_row.source_cc_id;
                IF FOUND THEN
                    INSERT INTO scripts_curriculum_merge_log (
                        run_id, stage, entity, source_id, target_id, reason_code
                    ) VALUES (
                        v_run_id,
                        'apply',
                        'curricourse',
                        v_row.source_cc_id,
                        v_row.target_cc_id,
                        'CURRICOURSE_DELETED'
                    );
                ELSE
                    INSERT INTO scripts_curriculum_merge_log (
                        run_id, stage, entity, source_id, target_id, reason_code
                    ) VALUES (
                        v_run_id,
                        'apply',
                        'curricourse',
                        v_row.source_cc_id,
                        v_row.target_cc_id,
                        'CURRICOURSE_DELETE_NOOP'
                    );
                END IF;
            EXCEPTION WHEN foreign_key_violation THEN
                INSERT INTO scripts_curriculum_merge_log (
                    run_id, stage, entity, source_id, target_id, reason_code
                ) VALUES (
                    v_run_id,
                    'apply',
                    'curricourse',
                    v_row.source_cc_id,
                    v_row.target_cc_id,
                    'CURRICOURSE_DELETE_PROTECTED'
                );
            END;
        END LOOP;

        IF EXISTS (
            SELECT 1
            FROM people_stdcurrienroll
            WHERE curriculum_id = v_source
        ) THEN
            INSERT INTO scripts_curriculum_merge_log (
                run_id, stage, entity, source_id, target_id, reason_code
            ) VALUES (
                v_run_id,
                'apply',
                'curriculum',
                v_source,
                v_target,
                'CURRICULUM_DELETE_BLOCKED_ENROLLMENT'
            );
        ELSE
            BEGIN
                DELETE FROM academics_curriculum WHERE id = v_source;
                IF FOUND THEN
                    INSERT INTO scripts_curriculum_merge_log (
                        run_id, stage, entity, source_id, target_id, reason_code
                    ) VALUES (
                        v_run_id,
                        'apply',
                        'curriculum',
                        v_source,
                        v_target,
                        'CURRICULUM_DELETED'
                    );
                ELSE
                    INSERT INTO scripts_curriculum_merge_log (
                        run_id, stage, entity, source_id, target_id, reason_code
                    ) VALUES (
                        v_run_id,
                        'apply',
                        'curriculum',
                        v_source,
                        v_target,
                        'CURRICULUM_DELETE_NOOP'
                    );
                END IF;
            EXCEPTION WHEN foreign_key_violation THEN
                INSERT INTO scripts_curriculum_merge_log (
                    run_id, stage, entity, source_id, target_id, reason_code
                ) VALUES (
                    v_run_id,
                    'apply',
                    'curriculum',
                    v_source,
                    v_target,
                    'CURRICULUM_DELETE_PROTECTED'
                );
            END;
        END IF;
    END IF;

    UPDATE scripts_curriculum_merge_run
    SET finished_at = NOW(),
        status = 'success',
        note = CASE
            WHEN v_apply THEN 'apply run completed'
            ELSE 'dry-run preflight completed'
        END
    WHERE run_id = v_run_id;

EXCEPTION
    WHEN OTHERS THEN
        UPDATE scripts_curriculum_merge_run
        SET finished_at = NOW(),
            status = 'failed',
            note = SQLERRM
        WHERE run_id = v_run_id;
END
$$;

-- Run header.
SELECT
    run_id,
    run_label,
    source_curriculum_id,
    target_curriculum_id,
    apply_mode,
    status,
    started_at,
    finished_at,
    note
FROM scripts_curriculum_merge_run
WHERE run_id = :run_id;

-- Reason summary.
SELECT
    stage,
    entity,
    reason_code,
    COUNT(*) AS row_count
FROM scripts_curriculum_merge_log
WHERE run_id = :run_id
GROUP BY stage, entity, reason_code
ORDER BY stage, entity, reason_code;

-- Focus on conflicts/blockers/protected rows.
SELECT
    log_id,
    stage,
    entity,
    source_id,
    target_id,
    section_id,
    student_id,
    reason_code,
    detail,
    created_at
FROM scripts_curriculum_merge_log
WHERE run_id = :run_id
  AND (
      reason_code LIKE '%BLOCK%'
      OR reason_code LIKE '%CONFLICT%'
      OR reason_code LIKE '%PROTECTED%'
      OR reason_code LIKE '%SKIPPED%'
      OR reason_code = 'SECTION_DUPLICATE_STUDENT_GRADE'
  )
ORDER BY log_id;
