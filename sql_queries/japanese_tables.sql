-- =============================================================================
-- Japanese Unicode Validation — DDL + seed data + control rule
-- Run order: Step 1 → Step 2 → Step 3 → Step 4 (verify)
-- =============================================================================


-- =============================================================================
-- STEP 1: Create source table  (data as it arrived — with encoding problems)
-- =============================================================================
DROP TABLE IF EXISTS public.jp_customers_source CASCADE;

CREATE TABLE jp_customers_source (
    customer_id   SERIAL PRIMARY KEY,
    name_jp       TEXT,
    product_jp    TEXT,
    city_jp       TEXT
);


-- =============================================================================
-- STEP 2: Create target table  (clean, fully normalised reference)
-- =============================================================================
DROP TABLE IF EXISTS jp_customers_target CASCADE;

CREATE TABLE jp_customers_target (
    customer_id   INT PRIMARY KEY,
    name_jp       TEXT,
    product_jp    TEXT,
    city_jp       TEXT
);


-- =============================================================================
-- STEP 3: Insert rows
-- =============================================================================

-- ── Source rows ───────────────────────────────────────────────────────────────
-- Row 1: Clean — will PASS
-- Row 2: Half-width katakana (ｽｽﾞｷ vs スズキ) — PASSES under NFKC (folds to same)
-- Row 3: Replacement character U+FFFD embedded in name — will FAIL
-- Row 4: Mojibake — UTF-8 Japanese bytes decoded as Latin-1 — will FAIL
-- Row 5: Plain value mismatch (different person) — will FAIL
-- Row 6: Clean — will PASS

INSERT INTO jp_customers_source (name_jp, product_jp, city_jp)
VALUES
    -- 1: clean
    ('田中太郎',       'ノートパソコン',  '東京都'),

    -- 2: half-width katakana  ｽｽﾞｷ花子 / ﾉｰﾄﾊﾟｿｺﾝ
    (U&'\FF75\FF75\FF9E\FF77\82B1\5B50',
     U&'\FF89\FF70\FF84\FF8A\FF9F\FF7C\FF52\FF9D',
     '大阪府'),

    -- 3: replacement character U+FFFD inside the name
    (U&'\4F50\85E4\FFFD\4E00\90CE',  'タブレット',     '京都府'),

    -- 4: mojibake — UTF-8 bytes of 高橋太郎 / テレビ decoded as Latin-1
    --    高橋太郎 in UTF-8: E9 AB 98 E6 A9 8B E5 A4 AA E9 82 B4
    --    テレビ   in UTF-8: E3 83 86 E3 83 AC E3 83 93
    (U&'\00E9\00AB\0098\00E6\00A9\008B\00E5\00A4\00AA\00E9\0082\00B4',
     U&'\00E3\0083\0086\00E3\0083\00AC\00E3\0083\0093',
     '北海道'),

    -- 5: value mismatch — 渡辺健二 in source vs 鈴木健二 in target
    ('渡辺健二',       'スマートフォン',  '福岡県'),

    -- 6: clean
    ('山田花子',       'キーボード',      '沖縄県');


-- ── Target rows (clean reference) ────────────────────────────────────────────
INSERT INTO jp_customers_target (customer_id, name_jp, product_jp, city_jp)
VALUES
    (1, '田中太郎',   'ノートパソコン',  '東京都'),  -- 1 clean match
    (2, 'スズキ花子',  'ノートパソコン',  '大阪府'),  -- 2 full-width katakana (correct form)
    (3, '佐藤一郎',   'タブレット',      '京都府'),  -- 3 no replacement char
    (4, '高橋太郎',   'テレビ',          '北海道'),  -- 4 clean Japanese
    (5, '鈴木健二',   'スマートフォン',  '福岡県'),  -- 5 correct name
    (6, '山田花子',   'キーボード',      '沖縄県');  -- 6 clean match


-- =============================================================================
-- STEP 4: Insert the DQ control rule
--         target_df stores the TARGET TABLE NAME as a string.
--         The DQRunner resolves it to a live DataFrame via read_table().
-- =============================================================================
INSERT INTO dq_control
    (schema_name, table_name, dqmethod, config, is_active)
VALUES (
    'public',
    'jp_customers_source',
    'UnicodeValidationEval',
    '{
        "key_column":         "customer_id",
        "columns":            ["name_jp", "product_jp", "city_jp"],
        "target_df":          "jp_customers_target",
        "normalization_form": "NFKC",
        "batch_size":         1000
    }'::jsonb,
    TRUE
);


-- =============================================================================
-- VERIFY: Check what was inserted
-- =============================================================================

-- Source table
SELECT 'SOURCE' AS tbl, customer_id, name_jp, product_jp, city_jp
FROM   jp_customers_source
ORDER  BY customer_id;

-- Target table
SELECT 'TARGET' AS tbl, customer_id, name_jp, product_jp, city_jp
FROM   jp_customers_target
ORDER  BY customer_id;

-- Control rule
SELECT control_id, schema_name, table_name, dqmethod, config, is_active
FROM   dq_control
WHERE  table_name = 'jp_customers_source';
