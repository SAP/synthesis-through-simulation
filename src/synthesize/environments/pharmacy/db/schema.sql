-- Pharmacy Management System schema

CREATE TABLE IF NOT EXISTS patient (
    patient_id      TEXT PRIMARY KEY,
    name            TEXT NOT NULL,
    date_of_birth   TEXT NOT NULL,
    email           TEXT UNIQUE,
    phone           TEXT,
    medical_history TEXT,
    is_active       INTEGER NOT NULL DEFAULT 1
);

CREATE TABLE IF NOT EXISTS physician (
    physician_id      TEXT PRIMARY KEY,
    name              TEXT NOT NULL,
    license_number    TEXT NOT NULL UNIQUE,
    email             TEXT UNIQUE,
    affiliated_clinic TEXT,
    specialty         TEXT,
    is_active         INTEGER NOT NULL DEFAULT 1
);

CREATE TABLE IF NOT EXISTS medication (
    medication_id        TEXT PRIMARY KEY,
    name                 TEXT NOT NULL,
    form                 TEXT NOT NULL,   -- 'tablet', 'capsule', 'liquid', 'injection', 'topical'
    strength             TEXT NOT NULL,
    manufacturer         TEXT,
    classification       TEXT NOT NULL,   -- 'OTC', 'prescription', 'controlled'
    storage_requirements TEXT,
    is_active            INTEGER NOT NULL DEFAULT 1
);

CREATE TABLE IF NOT EXISTS prescription (
    prescription_id   TEXT PRIMARY KEY,
    patient_id        TEXT NOT NULL REFERENCES patient(patient_id),
    physician_id      TEXT NOT NULL REFERENCES physician(physician_id),
    medication_id     TEXT NOT NULL REFERENCES medication(medication_id),
    dosage            TEXT NOT NULL,
    instructions      TEXT NOT NULL,
    date_issued       TEXT NOT NULL,
    date_filled       TEXT,
    status            TEXT NOT NULL DEFAULT 'pending',
    -- 'pending', 'filled', 'on_hold', 'cancelled', 'expired'
    pharmacy_notes    TEXT,
    refills_remaining INTEGER NOT NULL DEFAULT 0
);

CREATE INDEX IF NOT EXISTS idx_prescription_patient  ON prescription(patient_id);
CREATE INDEX IF NOT EXISTS idx_prescription_physician ON prescription(physician_id);
