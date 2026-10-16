-- Airline Mock Database Schema
-- Generated for synthesis testing of the tau2-bench airline domain

PRAGMA foreign_keys = ON;

-- ============================================================================
-- USERS
-- ============================================================================
CREATE TABLE IF NOT EXISTS users (
    user_id         TEXT PRIMARY KEY,
    first_name      TEXT NOT NULL,
    last_name       TEXT NOT NULL,
    email           TEXT NOT NULL,
    dob             TEXT NOT NULL,  -- YYYY-MM-DD
    membership      TEXT NOT NULL DEFAULT 'regular'
                    CHECK (membership IN ('gold', 'silver', 'regular')),
    -- Address fields
    address1        TEXT NOT NULL,
    address2        TEXT,
    city            TEXT NOT NULL,
    state           TEXT NOT NULL,
    country         TEXT NOT NULL,
    zip             TEXT NOT NULL,
    created_at      TEXT DEFAULT (datetime('now'))
);

CREATE INDEX idx_users_email ON users(email);
CREATE INDEX idx_users_membership ON users(membership);

-- ============================================================================
-- PAYMENT METHODS (credit_card, gift_card, certificate)
-- ============================================================================
CREATE TABLE IF NOT EXISTS payment_methods (
    payment_method_id   TEXT PRIMARY KEY,
    user_id             TEXT NOT NULL REFERENCES users(user_id) ON DELETE CASCADE,
    source              TEXT NOT NULL CHECK (source IN ('credit_card', 'gift_card', 'certificate')),
    -- credit card fields (NULL for non-credit-card)
    brand               TEXT,     -- visa, mastercard, etc.
    last_four           TEXT,
    -- balance fields (for gift_card / certificate)
    amount              REAL DEFAULT 0,
    created_at          TEXT DEFAULT (datetime('now'))
);

CREATE INDEX idx_payment_methods_user ON payment_methods(user_id);
CREATE INDEX idx_payment_methods_source ON payment_methods(source);

-- ============================================================================
-- SAVED PASSENGERS (user's saved passenger profiles)
-- ============================================================================
CREATE TABLE IF NOT EXISTS saved_passengers (
    id              INTEGER PRIMARY KEY AUTOINCREMENT,
    user_id         TEXT NOT NULL REFERENCES users(user_id) ON DELETE CASCADE,
    first_name      TEXT NOT NULL,
    last_name       TEXT NOT NULL,
    dob             TEXT NOT NULL  -- YYYY-MM-DD
);

CREATE INDEX idx_saved_passengers_user ON saved_passengers(user_id);

-- ============================================================================
-- FLIGHTS (route-level data)
-- ============================================================================
CREATE TABLE IF NOT EXISTS flights (
    flight_number                   TEXT PRIMARY KEY,
    origin                          TEXT NOT NULL,
    destination                     TEXT NOT NULL,
    scheduled_departure_time_est    TEXT NOT NULL,  -- HH:MM:SS
    scheduled_arrival_time_est      TEXT NOT NULL   -- HH:MM:SS (may include +1)
);

CREATE INDEX idx_flights_origin ON flights(origin);
CREATE INDEX idx_flights_destination ON flights(destination);
CREATE INDEX idx_flights_route ON flights(origin, destination);

-- ============================================================================
-- FLIGHT DATES (per-date status and availability for each flight)
-- ============================================================================
CREATE TABLE IF NOT EXISTS flight_dates (
    id                  INTEGER PRIMARY KEY AUTOINCREMENT,
    flight_number       TEXT NOT NULL REFERENCES flights(flight_number) ON DELETE CASCADE,
    date                TEXT NOT NULL,  -- YYYY-MM-DD
    status              TEXT NOT NULL DEFAULT 'available'
                        CHECK (status IN ('available', 'on time', 'flying', 'landed', 'cancelled', 'delayed')),
    -- available seats (only relevant when status='available')
    seats_business      INTEGER DEFAULT 0,
    seats_economy       INTEGER DEFAULT 0,
    seats_basic_economy INTEGER DEFAULT 0,
    -- prices (only relevant when status='available')
    price_business      INTEGER DEFAULT 0,
    price_economy       INTEGER DEFAULT 0,
    price_basic_economy INTEGER DEFAULT 0,
    -- timing fields (for non-available statuses)
    estimated_departure_time_est  TEXT,
    estimated_arrival_time_est    TEXT,
    actual_departure_time_est     TEXT,
    actual_arrival_time_est       TEXT,
    UNIQUE(flight_number, date)
);

CREATE INDEX idx_flight_dates_flight ON flight_dates(flight_number);
CREATE INDEX idx_flight_dates_date ON flight_dates(date);
CREATE INDEX idx_flight_dates_status ON flight_dates(status);
CREATE INDEX idx_flight_dates_route_date ON flight_dates(flight_number, date);

-- ============================================================================
-- RESERVATIONS
-- ============================================================================
CREATE TABLE IF NOT EXISTS reservations (
    reservation_id  TEXT PRIMARY KEY,
    user_id         TEXT NOT NULL REFERENCES users(user_id),
    origin          TEXT NOT NULL,
    destination     TEXT NOT NULL,
    flight_type     TEXT NOT NULL CHECK (flight_type IN ('round_trip', 'one_way')),
    cabin           TEXT NOT NULL CHECK (cabin IN ('business', 'economy', 'basic_economy')),
    total_baggages  INTEGER NOT NULL DEFAULT 0,
    nonfree_baggages INTEGER NOT NULL DEFAULT 0,
    insurance       TEXT NOT NULL DEFAULT 'no' CHECK (insurance IN ('yes', 'no')),
    status          TEXT DEFAULT NULL CHECK (status IS NULL OR status = 'cancelled'),
    created_at      TEXT DEFAULT (datetime('now'))
);

CREATE INDEX idx_reservations_user ON reservations(user_id);
CREATE INDEX idx_reservations_status ON reservations(status);

-- ============================================================================
-- RESERVATION FLIGHTS (flights within a reservation)
-- ============================================================================
CREATE TABLE IF NOT EXISTS reservation_flights (
    id              INTEGER PRIMARY KEY AUTOINCREMENT,
    reservation_id  TEXT NOT NULL REFERENCES reservations(reservation_id) ON DELETE CASCADE,
    flight_number   TEXT NOT NULL,
    origin          TEXT NOT NULL,
    destination     TEXT NOT NULL,
    date            TEXT NOT NULL,  -- YYYY-MM-DD
    price           INTEGER NOT NULL
);

CREATE INDEX idx_reservation_flights_reservation ON reservation_flights(reservation_id);

-- ============================================================================
-- RESERVATION PASSENGERS
-- ============================================================================
CREATE TABLE IF NOT EXISTS reservation_passengers (
    id              INTEGER PRIMARY KEY AUTOINCREMENT,
    reservation_id  TEXT NOT NULL REFERENCES reservations(reservation_id) ON DELETE CASCADE,
    first_name      TEXT NOT NULL,
    last_name       TEXT NOT NULL,
    dob             TEXT NOT NULL  -- YYYY-MM-DD
);

CREATE INDEX idx_reservation_passengers_reservation ON reservation_passengers(reservation_id);

-- ============================================================================
-- PAYMENT HISTORY (payments made for reservations)
-- ============================================================================
CREATE TABLE IF NOT EXISTS payment_history (
    id              INTEGER PRIMARY KEY AUTOINCREMENT,
    reservation_id  TEXT NOT NULL REFERENCES reservations(reservation_id) ON DELETE CASCADE,
    payment_id      TEXT NOT NULL,  -- references payment_method_id
    amount          INTEGER NOT NULL,
    created_at      TEXT DEFAULT (datetime('now'))
);

CREATE INDEX idx_payment_history_reservation ON payment_history(reservation_id);
