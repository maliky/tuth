-- Fix payment status FK violations during finance.0004 migration.
-- Run once BEFORE migrate (backs up and truncates payments),
-- then run again AFTER migrate (seeds paymentstatus + restores payments).

BEGIN;
DO $$
BEGIN
  IF to_regclass('public.tmp_finance_payment_backup') IS NULL THEN
    CREATE TABLE tmp_finance_payment_backup AS TABLE finance_payment;
    TRUNCATE TABLE finance_payment CASCADE;
  END IF;
END $$;
COMMIT;

BEGIN;
DO $$
BEGIN
  IF to_regclass('public.finance_paymentstatus') IS NOT NULL
     AND to_regclass('public.tmp_finance_payment_backup') IS NOT NULL THEN
    INSERT INTO finance_paymentstatus (code, label)
    VALUES ('pending', 'Pending'), ('cleared', 'Cleared')
    ON CONFLICT DO NOTHING;

    INSERT INTO finance_payment (
      id,
      invoice_id,
      amount_paid,
      payment_method_id,
      status_id,
      recorded_by_id
    )
    SELECT
      id,
      invoice_id,
      amount_paid,
      payment_method_id,
      CASE
        WHEN status_id = 'cleared' THEN 'cleared'
        ELSE 'pending'
      END AS status_id,
      recorded_by_id
    FROM tmp_finance_payment_backup;

    PERFORM setval(
      pg_get_serial_sequence('finance_payment', 'id'),
      COALESCE((SELECT MAX(id) FROM finance_payment), 1),
      true
    );

    DROP TABLE tmp_finance_payment_backup;
  END IF;
END $$;
COMMIT;

-- Post-restore sanity checks.
SELECT to_regclass('public.finance_payment') IS NOT NULL AS payment_exists \gset
\if :payment_exists
SELECT status_id, COUNT(*) AS total
FROM finance_payment
GROUP BY status_id
ORDER BY status_id;
\else
\echo 'finance_payment does not exist yet.'
\endif

SELECT to_regclass('public.finance_paymentstatus') IS NOT NULL AS paymentstatus_exists \gset
\if :paymentstatus_exists
SELECT code
FROM finance_paymentstatus
ORDER BY code;
\else
\echo 'finance_paymentstatus does not exist yet.'
\endif
