-- Generic Mock Database Schema
-- Generated for synthesis testing of the tau2-bench generic domain

PRAGMA foreign_keys = ON;

-- ============================================================================
-- OBJECT_FS
-- ============================================================================
CREATE TABLE IF NOT EXISTS object_fs (
    property_id         TEXT PRIMARY KEY,
    property_n      TEXT NOT NULL,
    property_o      TEXT NOT NULL,
    property_p      TEXT NOT NULL,
    property_m      TEXT NOT NULL,  -- YYYY-MM-DD
    property_q      TEXT NOT NULL DEFAULT 'value_r'
                    CHECK (property_q IN ('value_g', 'value_s', 'value_r')),
    -- property_r through property_w
    property_r      TEXT NOT NULL,
    property_s      TEXT,
    property_t      TEXT NOT NULL,
    property_u      TEXT NOT NULL,
    property_v      TEXT NOT NULL,
    property_w      TEXT NOT NULL,
    created_at      TEXT DEFAULT (datetime('now'))
);

CREATE INDEX idx_object_fs_property_p ON object_fs(property_p);
CREATE INDEX idx_object_fs_property_q ON object_fs(property_q);

-- ============================================================================
-- OBJECT_ES (i_a, i_b, i_c)
-- ============================================================================
CREATE TABLE IF NOT EXISTS object_es (
    object_e_id         TEXT PRIMARY KEY,
    property_id             TEXT NOT NULL REFERENCES object_fs(property_id) ON DELETE CASCADE,
    property_i          TEXT NOT NULL CHECK (property_i IN ('i_a', 'i_b', 'i_c')),
    -- i_a fields (NULL for non-i_a)
    property_j          TEXT,     -- value_a, value_b, etc.
    property_k          TEXT,
    -- amount fields (for i_b / i_c)
    amount              REAL DEFAULT 0,
    created_at          TEXT DEFAULT (datetime('now'))
);

CREATE INDEX idx_object_es_user ON object_es(property_id);
CREATE INDEX idx_object_es_type ON object_es(property_i);

-- ============================================================================
-- SAVED OBJECT_DS (object_f's saved object_d profiles)
-- ============================================================================
CREATE TABLE IF NOT EXISTS saved_object_ds (
    id              INTEGER PRIMARY KEY AUTOINCREMENT,
    property_id         TEXT NOT NULL REFERENCES object_fs(property_id) ON DELETE CASCADE,
    property_n      TEXT NOT NULL,
    property_o      TEXT NOT NULL,
    property_m      TEXT NOT NULL  -- YYYY-MM-DD
);

CREATE INDEX idx_saved_object_ds_user ON saved_object_ds(property_id);

-- ============================================================================
-- OBJECT_BS (object data)
-- ============================================================================
CREATE TABLE IF NOT EXISTS object_bs (
    object_b_number             TEXT PRIMARY KEY,
    object_a_property_1         TEXT NOT NULL,
    object_a_property_2         TEXT NOT NULL,
    scheduled_property_c        TEXT NOT NULL,  -- HH:MM:SS
    scheduled_property_d        TEXT NOT NULL   -- HH:MM:SS (may include +1)
);

CREATE INDEX idx_object_bs_object_a_property_1 ON object_bs(object_a_property_1);
CREATE INDEX idx_object_bs_object_a_property_2 ON object_bs(object_a_property_2);
CREATE INDEX idx_object_bs_obj_a ON object_bs(object_a_property_1, object_a_property_2);

-- ============================================================================
-- OBJECT_B PROPERTY_LS (per-property_l status and availability for each object_b)
-- ============================================================================
CREATE TABLE IF NOT EXISTS object_b_property_ls (
    id                  INTEGER PRIMARY KEY AUTOINCREMENT,
    object_b_number       TEXT NOT NULL REFERENCES object_bs(object_b_number) ON DELETE CASCADE,
    property_l          TEXT NOT NULL,  -- YYYY-MM-DD
    status              TEXT NOT NULL DEFAULT 'available'
                        CHECK (status IN ('status_a', 'status_b', 'status_c', 'status_d', 'status_e', 'status_f')),
    -- property_a availability (only relevant when status='available')
    property_a_type_b      INTEGER DEFAULT 0,
    property_a_type_a       INTEGER DEFAULT 0,
    property_a_type_c INTEGER DEFAULT 0,
    -- property_b values (only relevant when status='available')
    property_b_type_b      INTEGER DEFAULT 0,
    property_b_type_a       INTEGER DEFAULT 0,
    property_b_type_c INTEGER DEFAULT 0,
    -- timing fields (for non-available statuses)
    estimated_property_c  TEXT,
    estimated_property_d  TEXT,
    actual_property_c     TEXT,
    actual_property_d     TEXT,
    UNIQUE(object_b_number, property_l)
);

CREATE INDEX idx_object_b_property_ls_object_b ON object_b_property_ls(object_b_number);
CREATE INDEX idx_object_b_property_ls_property_l ON object_b_property_ls(property_l);
CREATE INDEX idx_object_b_property_ls_status ON object_b_property_ls(status);
CREATE INDEX idx_object_b_property_ls_object_b_pl ON object_b_property_ls(object_b_number, property_l);

-- ============================================================================
-- OBJECT_CS
-- ============================================================================
CREATE TABLE IF NOT EXISTS object_cs (
    object_c_id         TEXT PRIMARY KEY,
    property_id             TEXT NOT NULL REFERENCES object_fs(property_id),
    object_a_property_1 TEXT NOT NULL,
    object_a_property_2 TEXT NOT NULL,
    object_b_type       TEXT NOT NULL CHECK (object_b_type IN ('option_b', 'option_a')),
    property_e          TEXT NOT NULL CHECK (property_e IN ('type_b', 'type_a', 'type_c')),
    property_f          INTEGER NOT NULL DEFAULT 0,
    property_h          INTEGER NOT NULL DEFAULT 0,
    property_g          TEXT NOT NULL DEFAULT 'no' CHECK (property_g IN ('yes', 'no')),
    status              TEXT DEFAULT NULL CHECK (status IS NULL OR status = 'status_a'),
    created_at          TEXT DEFAULT (datetime('now'))
);

CREATE INDEX idx_object_cs_user ON object_cs(property_id);
CREATE INDEX idx_object_cs_status ON object_cs(status);

-- ============================================================================
-- OBJECT_C OBJECT_BS (object_bs within a object_c)
-- ============================================================================
CREATE TABLE IF NOT EXISTS object_c_object_bs (
    id                  INTEGER PRIMARY KEY AUTOINCREMENT,
    object_c_id         TEXT NOT NULL REFERENCES object_cs(object_c_id) ON DELETE CASCADE,
    object_b_number     TEXT NOT NULL,
    object_a_property_1 TEXT NOT NULL,
    object_a_property_2 TEXT NOT NULL,
    property_l          TEXT NOT NULL,  -- YYYY-MM-DD
    property_b          INTEGER NOT NULL
);

CREATE INDEX idx_object_c_object_bs_object_c ON object_c_object_bs(object_c_id);

-- ============================================================================
-- OBJECT_C OBJECT_DS
-- ============================================================================
CREATE TABLE IF NOT EXISTS object_c_object_ds (
    id              INTEGER PRIMARY KEY AUTOINCREMENT,
    object_c_id  TEXT NOT NULL REFERENCES object_cs(object_c_id) ON DELETE CASCADE,
    property_n      TEXT NOT NULL,
    property_o      TEXT NOT NULL,
    property_m      TEXT NOT NULL  -- YYYY-MM-DD
);

CREATE INDEX idx_object_c_object_ds_object_c ON object_c_object_ds(object_c_id);

-- ============================================================================
-- OBJECT_C OBJECT_ES (object_es used for object_cs)
-- ============================================================================
CREATE TABLE IF NOT EXISTS object_c_object_es (
    id              INTEGER PRIMARY KEY AUTOINCREMENT,
    object_c_id  TEXT NOT NULL REFERENCES object_cs(object_c_id) ON DELETE CASCADE,
    object_e_id     TEXT NOT NULL,  -- references object_e_id
    amount          INTEGER NOT NULL,
    created_at      TEXT DEFAULT (datetime('now'))
);

CREATE INDEX idx_object_c_object_es_object_c ON object_c_object_es(object_c_id);
