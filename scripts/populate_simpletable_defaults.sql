BEGIN;

-- academics_curristatus
INSERT INTO academics_curristatus (code, label) VALUES
    ('pending', 'Pending'),
    ('approved', 'Approved'),
    ('needs_revision', 'Needs Revision')
ON CONFLICT (code) DO UPDATE SET label = EXCLUDED.label;

-- registry_doctype
INSERT INTO registry_doctype (code, label) VALUES
    ('photo', 'Photo'),
    ('applet', 'Application Letter'),
    ('recls', 'Recommandation Last School'),
    ('reccom', 'Recommandation Community'),
    ('recrel', 'Recommandation Relgious Leaders'),
    ('medcert', 'Medical Certificat'),
    ('repcard', 'Report Card'),
    ('waec', 'Waec'),
    ('bill', 'Bill'),
    ('transcript', 'Transcript'),
    ('public', 'Public_signature'),
    ('other', 'Other Document')
ON CONFLICT (code) DO UPDATE SET label = EXCLUDED.label;

-- registry_docstatus
INSERT INTO registry_docstatus (code, label) VALUES
    ('pending', 'Pending'),
    ('approved', 'Approved'),
    ('adjustments_required', 'Adjustments Required'),
    ('rejected', 'Rejected')
ON CONFLICT (code) DO UPDATE SET label = EXCLUDED.label;

-- registry_transcriptrequeststatus
INSERT INTO registry_transcriptrequeststatus (code, label) VALUES
    ('pending', 'Pending'),
    ('processing', 'Processing'),
    ('completed', 'Completed'),
    ('on_hold', 'On hold')
ON CONFLICT (code) DO UPDATE SET label = EXCLUDED.label;

-- registry_registrationstatus
INSERT INTO registry_registrationstatus (code, label) VALUES
    ('pending', 'Pending Payment'),
    ('partialy_cleared', 'Partialy Cleared'),
    ('cleared', 'Totaly Cleared')
ON CONFLICT (code) DO UPDATE SET label = EXCLUDED.label;

-- timetable_semesterstatus
INSERT INTO timetable_semesterstatus (code, label) VALUES
    ('planning', 'Planning'),
    ('registration', 'Registration Open'),
    ('running', 'Registration Closed, Semester running'),
    ('locked', 'Registration Closed, Semester locked')
ON CONFLICT (code) DO UPDATE SET label = EXCLUDED.label;

-- finance_accounttype
INSERT INTO finance_accounttype (code, label) VALUES
    ('liability', 'Liability'),
    ('asset', 'Asset'),
    ('capital', 'Capital'),
    ('expense', 'Expense'),
    ('income', 'Income'),
    ('unknown', 'Unknown')
ON CONFLICT (code) DO UPDATE SET label = EXCLUDED.label;

-- finance_accountcharttype (type_id references finance_accounttype.code)
INSERT INTO finance_accountcharttype (code, label, type_id) VALUES
    ('account_payable', 'Account Payable', 'liability'),
    ('account_receivable', 'Account Receivable', 'liability'),
    ('Bank', 'Bank', 'liability'),
    ('Cash', 'Cash', 'liability'),
    ('Equity', 'Equity', 'liability'),
    ('Expense', 'Expense', 'liability'),
    ('fixed_asset', 'Fixed Asset', 'liability'),
    ('Income', 'Income', 'liability'),
    ('long_term_liability', 'Long Term Liability', 'liability'),
    ('other_current_asset', 'Other Current Asset', 'liability'),
    ('other_current_liability', 'Other Current Liability', 'liability'),
    ('other', 'Other', 'liability')
ON CONFLICT (code) DO UPDATE
SET label = EXCLUDED.label,
    type_id = COALESCE(finance_accountcharttype.type_id, EXCLUDED.type_id);

-- finance_feetype
INSERT INTO finance_feetype (code, label) VALUES
    ('activities', 'Activities'),
    ('athletics', 'Athletics'),
    ('biology_lab', 'Biology Lab'),
    ('chemistry_lab', 'Chemistry Lab'),
    ('clinical', 'Clinical'),
    ('credit_hour', 'Credit Hour'),
    ('dormitory', 'Dormitory'),
    ('enterpreneurship', 'Enterpreneurship'),
    ('entrepreneurship_education_i', 'Entrepreneurship Education I'),
    ('entrepreneurship_education_ii', 'Entrepreneurship Education II'),
    ('graduation', 'Graduation'),
    ('id_card', 'ID Card'),
    ('lab', 'Laboratory'),
    ('late_registration', 'Late Registration'),
    ('library', 'Library'),
    ('maintenance', 'Maintenance'),
    ('medical_surgical_lab', 'Medical Surgical Lab'),
    ('obstetric_nursing_lab', 'Obstetric Nursing Lab'),
    ('other', 'Other'),
    ('pe_tshirt', 'P.E. T-Shirt'),
    ('pediatric_lab', 'Pediatric Lab'),
    ('physics_lab', 'Physics Lab'),
    ('pre-registration_penalty', 'Pre-Registration Penalty'),
    ('re-admission', 'Re-Admission'),
    ('registration', 'Registration'),
    ('research', 'Research'),
    ('science_laboratory', 'Science Laboratory'),
    ('sports', 'Sports'),
    ('technology', 'Technology'),
    ('transcript', 'Transcript'),
    ('tuition', 'Tuition')
ON CONFLICT (code) DO UPDATE SET label = EXCLUDED.label;

-- finance_courseinvoicestatus
INSERT INTO finance_courseinvoicestatus (code, label) VALUES
    ('initial', 'Initial'),
    ('settled', 'Settled'),
    ('cleared', 'Cleared'),
    ('updated', 'Updated')
ON CONFLICT (code) DO UPDATE SET label = EXCLUDED.label;

-- finance_paymentstatus
INSERT INTO finance_paymentstatus (code, label) VALUES
    ('pending', 'Pending'),
    ('cleared', 'Cleared')
ON CONFLICT (code) DO UPDATE SET label = EXCLUDED.label;

-- finance_paymentmethod
INSERT INTO finance_paymentmethod (code, label) VALUES
    ('wire', 'Wire'),
    ('mobile', 'Mobile Money'),
    ('crypto_ada', 'Crypto Ada'),
    ('cash', 'Cash')
ON CONFLICT (code) DO UPDATE SET label = EXCLUDED.label;

COMMIT;
