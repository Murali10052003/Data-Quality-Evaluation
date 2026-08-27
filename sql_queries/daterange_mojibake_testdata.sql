-- =============================================================================
-- Test data for DateRangeEval and MojibakeEval
-- =============================================================================


-- =============================================================================
-- TABLE 1: event_log — for DateRangeEval testing
-- Has dates both inside and outside expected ranges.
-- =============================================================================
DROP TABLE IF EXISTS public.event_log CASCADE;

CREATE TABLE event_log (
    event_id    SERIAL PRIMARY KEY,
    event_name  VARCHAR(100),
    event_date  TIMESTAMP,
    category    VARCHAR(50)
);

INSERT INTO event_log (event_name, event_date, category) VALUES
-- Good dates (within 2025-01-01 to 2026-12-31)
('Product Launch',         '2025-03-15 10:00:00', 'Marketing'),
('Board Meeting',          '2025-06-20 14:00:00', 'Corporate'),
('Team Offsite',           '2025-09-01 09:00:00', 'HR'),
('Annual Review',          '2026-01-10 11:00:00', 'HR'),
('Q2 Planning',            '2026-04-05 08:30:00', 'Strategy'),
('Tech Conference',        '2026-07-22 09:00:00', 'Engineering'),
('Customer Summit',        '2026-08-15 10:00:00', 'Sales'),
('Holiday Party',          '2026-12-20 18:00:00', 'HR'),

-- Out-of-range dates (before 2025)
('Legacy Migration',       '2023-06-01 12:00:00', 'Engineering'),
('Old Contract Signed',    '2020-11-30 09:00:00', 'Legal'),
('Archive Backup',         '2019-01-15 03:00:00', 'IT'),

-- Out-of-range dates (after 2026)
('Future Roadmap',         '2027-03-01 10:00:00', 'Strategy'),
('Projected Launch',       '2028-06-15 09:00:00', 'Marketing'),

-- NULL date (will also fail)
('TBD Event',              NULL,                  'Unknown');


-- =============================================================================
-- TABLE 2: customer_feedback — for MojibakeEval testing
-- Has mojibake, replacement characters, and clean text.
-- =============================================================================
DROP TABLE IF EXISTS public.customer_feedback CASCADE;

CREATE TABLE customer_feedback (
    feedback_id   SERIAL PRIMARY KEY,
    customer_name VARCHAR(200),
    comment       TEXT,
    city          VARCHAR(100)
);

INSERT INTO customer_feedback (customer_name, comment, city) VALUES
-- Clean rows
('John Smith',      'Great product, very satisfied!',           'New York'),
('Maria Garcia',    'Fast delivery and good packaging.',        'Los Angeles'),
('Yuki Tanaka',     'とても良い製品です。ありがとう。',              '東京'),
('Hans Mueller',    'Sehr gutes Produkt, danke!',               'Berlin'),
('Pierre Dupont',   'Excellent service client.',                'Paris'),

-- Mojibake rows: UTF-8 bytes of accented chars decoded as Latin-1
-- "café" → "cafÃ©" (é = C3 A9 in UTF-8 → Ã© in Latin-1)
('René Lefèvre',   'Le cafÃ© Ã©tait excellent.',               'Lyon'),
-- "naïve" → "naÃ¯ve"
('François Morel',  'Approche naÃ¯ve mais efficace.',           'Marseille'),
-- "über" → "Ã¼ber"
('Jürgen Becker',   'Das ist Ã¼ber alle MaÃen gut.',           'München'),

-- Replacement character U+FFFD
('Test User 1',     E'Product was good \uFFFD but had issues.', 'Chicago'),
('Test User 2',     E'Received item with \uFFFD damage.',       'Boston'),

-- Mixed: mojibake in customer_name
-- "José" → "JosÃ©"
(E'Jos\u00C3\u00A9 Hernandez', 'Nice product.',                'Madrid'),

-- Clean non-ASCII (should pass — proper Unicode, no mojibake)
('Ólafur Jónsson',  'Frábært!',                                 'Reykjavik'),
('Müller Schmidt',  'Alles in Ordnung.',                        'Wien'),
('Björk Lúðvíks',  'Mjög gott.',                               'Akureyri');


-- =============================================================================
-- DQ Control rules for the new tables
-- =============================================================================

-- DateRangeEval: check event_date is within 2025-01-01 to 2026-12-31
INSERT INTO dq_control (schema_name, table_name, dqmethod, config, is_active) VALUES
('public', 'event_log', 'DateRangeEval',
 '{"column": "event_date", "min_date": "2025-01-01", "max_date": "2026-12-31"}'::jsonb,
 TRUE);

-- MojibakeEval: check comment column for garbled text
INSERT INTO dq_control (schema_name, table_name, dqmethod, config, is_active) VALUES
('public', 'customer_feedback', 'MojibakeEval',
 '{"column": "comment"}'::jsonb,
 TRUE);

-- MojibakeEval: also check customer_name column
INSERT INTO dq_control (schema_name, table_name, dqmethod, config, is_active) VALUES
('public', 'customer_feedback', 'MojibakeEval',
 '{"column": "customer_name"}'::jsonb,
 TRUE);


-- =============================================================================
-- Verify
-- =============================================================================
-- SELECT * FROM event_log;
-- SELECT * FROM customer_feedback;
-- SELECT * FROM dq_control WHERE dqmethod IN ('DateRangeEval', 'MojibakeEval');


select * from event_log;
select * from customer_feedback;
select * from dq_control;


select event_date from event_log where 