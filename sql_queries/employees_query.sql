-- DROP TABLE IF EXISTS employee;

CREATE TABLE employee_1million (
    id INT,
    name VARCHAR(100),
    age INT,
    email VARCHAR(150),
    department VARCHAR(50),
    salary DECIMAL(10,2),
    label VARCHAR(20),
    created_at TIMESTAMP,
    user_id INT,
    score INT,
    country VARCHAR(10)
);

-- DROP TABLE employee

CREATE TABLE employee_lowdata (
    id INT,
    name VARCHAR(100),
    age INT,
    email VARCHAR(150),
    department VARCHAR(50),
    salary DECIMAL(10,2),
    label VARCHAR(20),
    created_at TIMESTAMP,
    user_id INT,
    score INT,
    country VARCHAR(10)
);


INSERT INTO employee_lowdata VALUES
(1,'John',25,'john@test.com','HR',70000,'A','2026-07-03 09:00:00',101,90,'US'),
(2,'Mary',30,'mary@test.com','Finance',72000,'A','2026-07-03 09:15:00',102,85,'US'),
(3,'David',40,'david@test.com','Engineering',75000,'B','2026-07-03 08:45:00',103,88,'US'),
(4,'Lisa',28,'lisa@test.com','HR',68000,'A','2026-07-03 08:30:00',104,91,'US'),
(5,'Kevin',35,'kevin@test.com','Finance',71000,'A','2026-07-03 09:20:00',105,95,'US'),
(6,'Emma',29,'emma@test.com','Engineering',69000,'B','2026-07-03 09:10:00',106,80,'US'),
(7,'Chris',45,'chris@test.com','HR',76000,'A','2026-07-03 09:05:00',107,89,'US'),
(8,'Sophia',31,'sophia@test.com','Engineering',73000,'B','2026-07-03 09:25:00',108,84,'US'),
(9,'James',26,'james@test.com','Finance',70500,'A','2026-07-03 09:40:00',109,92,'US'),
(10,'Olivia',33,'olivia@test.com','HR',71500,'A','2026-07-03 09:50:00',110,87,'US'),

-- Duplicate ID
(1,'Duplicate',38,'duplicate@test.com','HR',70000,'A','2026-07-03 09:30:00',111,90,'US'),

-- Empty Name
(11,NULL,27,'nullname@test.com','Engineering',69000,'B','2026-07-03 09:40:00',112,81,'US'),

-- Duplicate Email
(12,'EmailDup',32,'john@test.com','Finance',71000,'A','2026-07-03 09:55:00',113,86,'US'),

-- Invalid Email
(13,'BadEmail',30,'bademail.com','HR',72000,'A','2026-07-03 09:45:00',114,82,'US'),

-- Age Below Range
(14,'Minor',15,'minor@test.com','Engineering',65000,'B','2026-07-03 09:35:00',115,75,'US'),

-- Age Above Range
(15,'Senior',70,'senior@test.com','HR',72000,'A','2026-07-03 09:50:00',116,88,'US'),

-- Invalid Department
(16,'GamingGuy',29,'gaming@test.com','Gaming',70000,'A','2026-07-03 09:40:00',117,84,'US'),

-- Salary Drift
(17,'Rich',34,'rich@test.com','Finance',200000,'B','2026-07-03 09:30:00',118,99,'US'),

-- Label imbalance
(18,'Label1',28,'label1@test.com','HR',69000,'A','2026-07-03 09:20:00',119,85,'US'),
(19,'Label2',29,'label2@test.com','HR',69000,'A','2026-07-03 09:21:00',120,86,'US'),
(20,'Label3',30,'label3@test.com','HR',69000,'A','2026-07-03 09:22:00',121,87,'US'),
(21,'Label4',31,'label4@test.com','HR',69000,'A','2026-07-03 09:23:00',122,88,'US'),
(22,'Label5',32,'label5@test.com','HR',69000,'A','2026-07-03 09:24:00',123,89,'US'),
(23,'Label6',33,'label6@test.com','HR',69000,'A','2026-07-03 09:25:00',124,90,'US'),

-- Old Timestamp
(24,'OldData',28,'old@test.com','Finance',70000,'B','2024-01-01 00:00:00',125,80,'US'),

-- Invalid user_id
(25,'InvalidRef',27,'invalid@test.com','Engineering',71000,'A','2026-07-03 09:40:00',9999,90,'US'),

-- Negative Score
(26,'NegativeScore',29,'negative@test.com','HR',70000,'B','2026-07-03 09:40:00',126,-10,'US'),

-- Custom Validation Failure
(27,'IndiaUser',22,'india@test.com','Finance',70000,'A','2026-07-03 09:40:00',127,80,'IN'),

-- Valid Rows
(28,'Robert',35,'robert@test.com','Engineering',71000,'B','2026-07-03 09:40:00',128,92,'US'),
(29,'Alice',36,'alice@test.com','Finance',70500,'A','2026-07-03 09:40:00',129,94,'US'),
(30,'Bob',38,'bob@test.com','HR',71500,'B','2026-07-03 09:40:00',130,96,'US');

CREATE TABLE users_lowdata (
    id INT PRIMARY KEY
);

INSERT INTO users_lowdata VALUES
(101),(102),(103),(104),(105),(106),(107),(108),(109),(110),
(111),(112),(113),(114),(115),(116),(117),(118),(119),(120),
(121),(122),(123),(124),(125),(126),(127),(128),(129),(130);
-- select * from employee;


-- SELECT current_database();

-- SELECT 
--     r.run_id,
--     r.table_name,
--     r.dqmethod,
--     r.col,
--     r.status,
--     r.dqevalcount,
--     f.row_data
-- FROM dq_results r
-- JOIN dq_failed_rows f
--     ON  r.run_id     = f.run_id
--     AND r.table_name = f.table_name
--     AND r.dqmethod   = f.dqmethod
--     AND r.col        = f.col
-- WHERE r.status = 'Failed'
-- ORDER BY r.table_name, r.dqmethod;



-- delete from employee;
select count(*) from employee;
select * from employee;
INSERT INTO employee_1million
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
FROM generate_series(1, 1000000) AS gs;





