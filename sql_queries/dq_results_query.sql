

-- describe dq_results;
DROP TABLE dq_results;

select * from employee;
delete from dq_failed_rows;

DELETE FROM dq_results;
ALTER TABLE dq_results DROP CONSTRAINT dq_results_pkey;
ALTER TABLE dq_results DROP COLUMN result_id;
ALTER TABLE dq_results ADD PRIMARY KEY (run_id);

CREATE TABLE dq_results (
    run_id         TEXT         NOT NULL,
    schema_name    TEXT         NOT NULL,
    table_name     TEXT         NOT NULL,
    dqmethod       TEXT         NOT NULL,
    col            TEXT         NOT NULL DEFAULT 'N/A',
    status         TEXT,
    run_timestamp  TIMESTAMPTZ,
    dqevalcount    BIGINT       DEFAULT 0,
    PRIMARY KEY (run_id, schema_name, table_name, dqmethod, col)
);





select table_name, dqmethod, col, dqevalcount from dq_results;
select * from dq_failed_rows limit 10;
select * from employee;
select * from dq_control;

delete from dq_results;

select count(*) from employee_10million;

select * from dq_results;

delete from dq_results where dqmethod='CustomEval' and col='score';