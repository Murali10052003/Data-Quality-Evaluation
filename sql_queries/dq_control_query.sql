CREATE TABLE dq_control (
    control_id SERIAL PRIMARY KEY,
    schema_name VARCHAR(100) NOT NULL,
    table_name VARCHAR(100) NOT NULL,
    dqmethod VARCHAR(100) NOT NULL,
    config JSONB NOT NULL,
    is_active BOOLEAN DEFAULT TRUE,
    created_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP
);

INSERT INTO dq_control
(schema_name, table_name, dqmethod, config)
VALUES

('public', 'employee_lowdata', 'DupEval',
 '{"columns":["id"]}'),

('public', 'employee_lowdata', 'EmptyEval',
 '{"columns":["name","age"]}'),

('public', 'employee_lowdata', 'UniqueEval',
 '{"columns":["id"]}'),

('public', 'employee_lowdata', 'DtypeEval',
 '{"columns":{"id":"int","name":"str","age":"int"}}'),

('public', 'employee_lowdata', 'StringFormatEval',
 '{"column":"email","pattern":"^[A-Za-z0-9._%+-]+@[A-Za-z0-9.-]+\\.[A-Za-z]{2,}$"}'),

('public', 'employee_lowdata', 'SchemaValidationEval',
 '{"expected_schema":{"id":"int","name":"object","age":"int"}}'),

('public', 'employee_lowdata', 'RangeEval',
 '{"column":"age","min":18,"max":65}'),

('public', 'employee_lowdata', 'CategoricalValuesEval',
 '{"column":"department","allowed_values":["HR","Finance","Engineering"]}'),

('public', 'employee_lowdata', 'StatisticalDistributionEval',
 '{"column":"salary","mode":"feature_drift","reference_stats":{"mean":70000,"std":5000},"tolerance":0.1}'),

('public', 'employee_lowdata', 'StatisticalDistributionEval',
 '{"column":"label","mode":"label_balance"}'),

('public', 'employee_lowdata', 'DataFreshnessEval',
 '{"column":"created_at","freshness_threshold":"-2h"}'),


('public', 'employee_lowdata', 'RowCountEval',
 '{"min":30,"max":100}'),

('public', 'employee_lowdata', 'CustomEval',
 '{"column":"score","func":"lambda x: x >= 0"}'),

('public', 'employee_lowdata', 'CustomEval',
 '{"func":"lambda row: row[''age''] >= 18 and row[''country''] == ''US''"}');

SELECT * FROM dq_control;
DELETE FROM dq_control where control_id=15 and control_id<=30;

delete from dq_control where control_id=22;


select * from users;

INSERT INTO dq_control
(schema_name, table_name, dqmethod, config)
VALUES

('public', 'employee_10million', 'CustomEval',
 '{"column":"score","func":"lambda x: x >= 0"}'),

('public', 'employee_10million', 'CustomEval',
 '{"func":"lambda row: row[''age''] >= 18 and row[''country''] == ''US''"}'),

('public', 'employee_10million', 'ReferentialIntegrityEval',
 '{"column":"user_id","reference_df":"users","reference_column":"id"}');



select * from dq_results;

select * from employee;

select * from dq_control;

DELETE FROM dq_results;
DELETE FROM dq_failed_rows;

select * from dq_results where status='Failed';

delete from dq_control;

select * from dq_control;
select * from employee; 


INSERT INTO dq_control
(schema_name, table_name, dqmethod, config)
VALUES

('public','customer','DupEval',
'{"columns":["customer_id"]}'),

('public','customer','EmptyEval',
'{"columns":["customer_name"]}'),

('public','customer','UniqueEval',
'{"columns":["email"]}'),

('public','customer','StringFormatEval',
'{"column":"email","pattern":"^[A-Za-z0-9._%+-]+@[A-Za-z0-9.-]+\\.[A-Za-z]{2,}$"}'),

('public','customer','RangeEval',
'{"column":"age","min":18,"max":100}'),

('public','customer','CategoricalValuesEval',
'{"column":"gender","allowed_values":["Male","Female","Other"]}'),

('public','customer','DataFreshnessEval',
'{"column":"created_at","freshness_threshold":"-24h"}');


select * from employee_lowdata;
select * from employee_failed_rows;
select * from customer_failed_rows;

delete from employee_failed_rows;
delete from customer_failed_rows;

INSERT INTO employee
SELECT
    CASE WHEN gs % 10000 = 0 THEN 1 ELSE gs END AS id,           -- ~100 duplicate IDs
    CASE WHEN gs % 5000 = 0 THEN NULL ELSE 'Employee_' || gs END AS name,  -- ~200 nulls
    CASE 
        WHEN gs % 8000 = 0 THEN 15                                -- age below range
        WHEN gs % 9000 = 0 THEN 70                                -- age above range
        ELSE 18 + (random() * 47)::INT
    END AS age,
    CASE WHEN gs % 7000 = 0 THEN 'bademail.com' 
         ELSE 'user' || gs || '@test.com' END AS email,
    CASE 
        WHEN gs % 6000 = 0 THEN 'Gaming'                          -- invalid dept
        ELSE (ARRAY['HR','Finance','Engineering'])[1 + (random()*2)::INT]
    END AS department,
    CASE WHEN gs % 3000 = 0 THEN 200000 
         ELSE (65000 + random() * 35000)::DECIMAL(10,2) END AS salary,
    (ARRAY['A','B'])[1 + (random())::INT] AS label,
    NOW() - (random() * INTERVAL '30 days') AS created_at,
    100 + gs AS user_id,
    CASE WHEN gs % 4000 = 0 THEN -10 
         ELSE (50 + random() * 50)::INT END AS score,
    'US' AS country
FROM generate_series(1, 100000000) AS gs;



INSERT INTO dq_control
(schema_name, table_name, dqmethod, config)
VALUES

('public', 'employee_100million', 'DupEval',
 '{"columns":["id"]}'),

('public', 'employee_100million', 'EmptyEval',
 '{"columns":["name","age"]}'),

('public', 'employee_100million', 'UniqueEval',
 '{"columns":["id"]}'),

('public', 'employee_100million', 'DtypeEval',
 '{"columns":{"id":"int","name":"str","age":"int"}}'),

('public', 'employee_100million', 'StringFormatEval',
 '{"column":"email","pattern":"^[A-Za-z0-9._%+-]+@[A-Za-z0-9.-]+\\.[A-Za-z]{2,}$"}'),

('public', 'employee_100million', 'SchemaValidationEval',
 '{"expected_schema":{"id":"int","name":"object","age":"int"}}'),

('public', 'employee_100million', 'RangeEval',
 '{"column":"age","min":18,"max":65}'),

('public', 'employee_100million', 'CategoricalValuesEval',
 '{"column":"department","allowed_values":["HR","Finance","Engineering"]}'),

('public', 'employee_100million', 'StatisticalDistributionEval',
 '{"column":"salary","mode":"feature_drift","reference_stats":{"mean":70000,"std":5000},"tolerance":0.1}'),

('public', 'employee_100million', 'StatisticalDistributionEval',
 '{"column":"label","mode":"label_balance"}'),

('public', 'employee_100million', 'DataFreshnessEval',
 '{"column":"created_at","freshness_threshold":"-2h"}'),


('public', 'employee_100million', 'RowCountEval',
 '{"min":30,"max":100}'),

('public', 'employee_100million', 'CustomEval',
 '{"column":"score","func":"lambda x: x >= 0"}'),

('public', 'employee_100million', 'CustomEval',
 '{"func":"lambda row: row[''age''] >= 18 and row[''country''] == ''US''"}');