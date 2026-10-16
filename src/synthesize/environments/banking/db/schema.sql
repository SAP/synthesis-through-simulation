-- Retail Banking System schema

CREATE TABLE IF NOT EXISTS customer (
    customer_id  TEXT PRIMARY KEY,
    name         TEXT NOT NULL,
    email        TEXT NOT NULL UNIQUE,
    phone        TEXT,
    address      TEXT,
    id_type      TEXT NOT NULL,   -- 'passport', 'driver_license', 'national_id'
    id_number    TEXT NOT NULL UNIQUE,
    is_active    INTEGER NOT NULL DEFAULT 1,
    created_date TEXT NOT NULL
);

CREATE TABLE IF NOT EXISTS account (
    account_id        TEXT PRIMARY KEY,
    customer_id       TEXT NOT NULL REFERENCES customer(customer_id),
    account_type      TEXT NOT NULL,   -- 'checking', 'savings', 'loan'
    balance           REAL NOT NULL DEFAULT 0.0,
    currency          TEXT NOT NULL DEFAULT 'USD',
    status            TEXT NOT NULL DEFAULT 'active',  -- 'active', 'frozen', 'closed'
    overdraft_allowed INTEGER NOT NULL DEFAULT 0,
    opening_date      TEXT NOT NULL
);

CREATE TABLE IF NOT EXISTS txn (
    txn_id        TEXT PRIMARY KEY,
    account_id    TEXT NOT NULL REFERENCES account(account_id),
    txn_type      TEXT NOT NULL,   -- 'deposit', 'withdrawal', 'transfer_in', 'transfer_out', 'fee'
    amount        REAL NOT NULL,
    balance_after REAL NOT NULL,
    description   TEXT,
    created_date  TEXT NOT NULL
);

CREATE INDEX IF NOT EXISTS idx_account_customer ON account(customer_id);
CREATE INDEX IF NOT EXISTS idx_txn_account ON txn(account_id);
