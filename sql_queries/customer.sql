INSERT INTO customer
SELECT
    CASE WHEN gs % 10000 = 0 THEN 1 ELSE gs END AS customer_id,           -- ~500 duplicate IDs
    CASE WHEN gs % 5000 = 0 THEN NULL ELSE 'Customer_' || gs END AS customer_name,  -- ~1000 nulls
    CASE WHEN gs % 7000 = 0 THEN 'bademail.com' 
         ELSE 'user' || gs || '@test.com' END AS email,                    -- ~714 invalid emails
    '98765' || LPAD((gs % 99999)::TEXT, 5, '0') AS phone,
    CASE 
        WHEN gs % 8000 = 0 THEN 15                                         -- age below range
        WHEN gs % 9000 = 0 THEN 110                                        -- age above range
        ELSE 18 + (random() * 82)::INT
    END AS age,
    CASE 
        WHEN gs % 6000 = 0 THEN 'Unknown'                                  -- invalid gender
        ELSE (ARRAY['Male','Female','Other'])[1 + (random()*2)::INT]
    END AS gender,
    (ARRAY['Chennai','Bangalore','Hyderabad','Mumbai','Delhi','Pune','Kolkata'])[1 + (random()*6)::INT] AS city,
    (ARRAY['India','India','India','India','US','UK','Canada'])[1 + (random()*6)::INT] AS country,
    CASE 
        WHEN gs % 3000 = 0 THEN '2024-01-01 00:00:00'::TIMESTAMP          -- stale/old records
        ELSE NOW() - (random() * INTERVAL '30 days')
    END AS created_at
FROM generate_series(1, 5000000) AS gs;