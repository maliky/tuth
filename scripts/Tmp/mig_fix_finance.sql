INSERT INTO finance_invoicestatus (code, label) VALUES ('initial', 'Initial') ON CONFLICT DO NOTHING;

INSERT INTO finance_invoicestatus (code, label) VALUES ('settled', 'Settled') ON CONFLICT DO NOTHING;

INSERT INTO finance_invoicestatus (code, label) VALUES ('updated', 'Updated') ON CONFLICT DO NOTHING;
