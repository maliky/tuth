INSERT INTO finance_clearancestatus (code, label) VALUES ('initial', 'Initial') ON CONFLICT DO NOTHING;

INSERT INTO finance_clearancestatus (code, label) VALUES ('settled', 'Settled') ON CONFLICT DO NOTHING;

INSERT INTO finance_clearancestatus (code, label) VALUES ('updated', 'Updated') ON CONFLICT DO NOTHING;
