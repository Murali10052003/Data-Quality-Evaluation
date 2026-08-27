SELECT table_name
FROM information_schema.tables
WHERE table_schema = 'public';


select count(*) from employee;
SELECT count(*) from customer;


select * from dq_control;
select * from dq_results;

drop table if exists employee_failed_rows;
drop table if exists customer_failed_rows;
select * from employee_lowdata;

delete from dq_control;
delete from dq_results;

select * from customer;
UPDATE dq_control 
SET config = '{"column":"salary","mode":"feature_drift","reference_stats":{"mean":70000,"std":5000},"tolerance":0.1}'
WHERE table_name = 'employee_lowdata' AND dqmethod = 'StatisticalDistributionEval';


CREATE TABLE orders_lowdata (
    order_id INT,
    customer_id INT,
    product_id INT,
    quantity INT,
    order_amount DECIMAL(10,2),
    order_status VARCHAR(30),
    order_date TIMESTAMP
);


INSERT INTO dq_control
(schema_name, table_name, dqmethod, config)
VALUES

('public','orders_lowdata','DupEval',
'{"columns":["order_id"]}'),

('public','orders_lowdata','RangeEval',
'{"column":"quantity","min":1,"max":100}'),

('public','orders_lowdata','RangeEval',
'{"column":"order_amount","min":0,"max":100000}'),

('public','orders_lowdata','CategoricalValuesEval',
'{"column":"order_status","allowed_values":["Pending","Shipped","Delivered","Cancelled"]}')


INSERT INTO orders_lowdata VALUES
(1001,101,501,2,1200.00,'Delivered','2026-07-12 09:00:00'),
(1002,102,502,1,800.00,'Pending','2026-07-12 09:05:00'),
(1003,103,503,5,2500.00,'Delivered','2026-07-12 09:10:00'),
(1004,104,504,3,1800.00,'Shipped','2026-07-12 09:15:00'),
(1005,105,505,2,950.00,'Cancelled','2026-07-12 09:20:00'),
(1006,106,506,4,3200.00,'Delivered','2026-07-12 09:25:00'),
(1007,107,507,1,600.00,'Pending','2026-07-12 09:30:00'),
(1008,108,508,2,1400.00,'Delivered','2026-07-12 09:35:00'),
(1009,109,509,6,4200.00,'Shipped','2026-07-12 09:40:00'),
(1010,110,510,3,1500.00,'Delivered','2026-07-12 09:45:00'),
(1011,111,511,5,5000.00,'Pending','2026-07-12 09:50:00'),
(1012,112,512,2,1700.00,'Delivered','2026-07-12 09:55:00'),
(1013,113,513,1,900.00,'Cancelled','2026-07-12 10:00:00'),
(1014,114,514,2,1100.00,'Delivered','2026-07-12 10:05:00'),
(1015,115,515,3,2400.00,'Shipped','2026-07-12 10:10:00'),
(1016,116,516,2,1350.00,'Delivered','2026-07-12 10:15:00'),
(1017,117,517,4,3000.00,'Pending','2026-07-12 10:20:00'),
(1018,118,518,2,1600.00,'Delivered','2026-07-12 10:25:00'),

-- Duplicate Order ID
(1001,119,519,1,1000.00,'Delivered','2026-07-12 10:30:00'),

-- Invalid Customer ID (Referential Integrity)
(1019,999,520,2,1800.00,'Delivered','2026-07-12 10:35:00'),

-- Quantity below allowed range
(1020,120,521,0,800.00,'Pending','2026-07-12 10:40:00'),

-- Negative Order Amount
(1021,121,522,3,-1500.00,'Delivered','2026-07-12 10:45:00'),

-- Invalid Order Status
(1022,122,523,2,1700.00,'Processing','2026-07-12 10:50:00'),

-- Old Order Date
(1023,123,524,2,2100.00,'Delivered','2024-01-01 09:00:00'),

-- Very Large Order Amount (Range Failure)
(1024,124,525,2,500000.00,'Delivered','2026-07-12 10:55:00');