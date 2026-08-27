CREATE TABLE product ( product_id INT, product_name VARCHAR(100), category VARCHAR(50), price DECIMAL(10,2), stock INT, supplier_email VARCHAR(150) );



INSERT INTO product
SELECT
    CASE
        WHEN gs % 10000 = 0 THEN 1
        ELSE gs
    END AS product_id,                                    -- ~100 duplicate product IDs

    CASE
        WHEN gs % 5000 = 0 THEN NULL
        ELSE 'Product_' || gs
    END AS product_name,                                  -- ~200 NULL product names

    CASE
        WHEN gs % 6000 = 0 THEN 'Gaming'                  -- Invalid category
        ELSE (
            ARRAY[
                'Electronics',
                'Clothing',
                'Books',
                'Furniture'
            ]
        )[1 + floor(random() * 4)::INT]
    END AS category,

    CASE
        WHEN gs % 7000 = 0 THEN -100                      -- Negative price
        WHEN gs % 9000 = 0 THEN 200000                    -- Price above allowed range
        ELSE ROUND((10 + random() * 5000)::numeric, 2)
    END AS price,

    CASE
        WHEN gs % 8000 = 0 THEN -5                        -- Negative stock
        ELSE floor(random() * 1000)::INT
    END AS stock,

    CASE
        WHEN gs % 7500 = 0 THEN 'supplier.com'            -- Invalid email
        ELSE 'supplier' || gs || '@company.com'
    END AS supplier_email

FROM generate_series(1, 10000) AS gs;


INSERT INTO dq_control
(schema_name, table_name, dqmethod, config)
VALUES

('public','product','DupEval',
'{"columns":["product_id"]}'),

('public','product','EmptyEval',
'{"columns":["product_name"]}'),

('public','product','UniqueEval',
'{"columns":["product_id"]}'),

('public','product','CategoricalValuesEval',
'{"column":"category","allowed_values":["Electronics","Clothing","Books","Furniture"]}'),

('public','product','RangeEval',
'{"column":"price","min":0,"max":100000}'),

('public','product','RangeEval',
'{"column":"stock","min":0,"max":10000}'),

('public','product','StringFormatEval',
'{"column":"supplier_email","pattern":"^[A-Za-z0-9._%+-]+@[A-Za-z0-9.-]+\\\\.[A-Za-z]{2,}$"}');