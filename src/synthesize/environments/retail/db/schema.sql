-- Retail Mock Database Schema

CREATE TABLE IF NOT EXISTS users (
    user_id         TEXT PRIMARY KEY,
    first_name      TEXT NOT NULL,
    last_name       TEXT NOT NULL,
    email           TEXT NOT NULL,
    address1        TEXT NOT NULL,
    address2        TEXT,
    city            TEXT NOT NULL,
    state           TEXT NOT NULL,
    country         TEXT NOT NULL,
    zip             TEXT NOT NULL,
    created_at      TEXT DEFAULT (datetime('now'))
);

CREATE INDEX IF NOT EXISTS idx_users_email ON users(email);
CREATE INDEX IF NOT EXISTS idx_users_name ON users(first_name, last_name);
CREATE INDEX IF NOT EXISTS idx_users_zip ON users(zip);

-- ============================================================================
-- PAYMENT METHODS (credit_card, gift_card, paypal)
-- ============================================================================
CREATE TABLE IF NOT EXISTS payment_methods (
    payment_method_id   TEXT PRIMARY KEY,
    user_id             TEXT NOT NULL REFERENCES users(user_id) ON DELETE CASCADE,
    source              TEXT NOT NULL CHECK (source IN ('credit_card', 'gift_card', 'paypal')),
    -- credit card fields (NULL for non-credit-card)
    brand               TEXT,
    last_four           TEXT,
    -- balance field (for gift_card only)
    balance             REAL DEFAULT 0,
    created_at          TEXT DEFAULT (datetime('now'))
);

CREATE INDEX IF NOT EXISTS idx_payment_methods_user ON payment_methods(user_id);
CREATE INDEX IF NOT EXISTS idx_payment_methods_source ON payment_methods(source);

-- ============================================================================
-- PRODUCTS (product-level data, e.g., "Laptop")
-- ============================================================================
CREATE TABLE IF NOT EXISTS products (
    product_id      TEXT PRIMARY KEY,
    name            TEXT NOT NULL,
    created_at      TEXT DEFAULT (datetime('now'))
);

CREATE INDEX IF NOT EXISTS idx_products_name ON products(name);

-- ============================================================================
-- VARIANTS (specific product variants with options)
-- ============================================================================
CREATE TABLE IF NOT EXISTS variants (
    item_id         TEXT PRIMARY KEY,
    product_id      TEXT NOT NULL REFERENCES products(product_id) ON DELETE CASCADE,
    options         TEXT NOT NULL,  -- JSON string: {"color": "blue", "size": "large"}
    available       INTEGER NOT NULL DEFAULT 1,  -- boolean: 1 = true, 0 = false
    price           REAL NOT NULL,
    created_at      TEXT DEFAULT (datetime('now'))
);

CREATE INDEX IF NOT EXISTS idx_variants_product ON variants(product_id);
CREATE INDEX IF NOT EXISTS idx_variants_available ON variants(available);

-- ============================================================================
-- ORDERS
-- ============================================================================
CREATE TABLE IF NOT EXISTS orders (
    order_id        TEXT PRIMARY KEY,
    user_id         TEXT NOT NULL REFERENCES users(user_id),
    -- Shipping address (may differ from user's default address)
    address1        TEXT NOT NULL,
    address2        TEXT,
    city            TEXT NOT NULL,
    state           TEXT NOT NULL,
    country         TEXT NOT NULL,
    zip             TEXT NOT NULL,
    -- Status
    status          TEXT NOT NULL DEFAULT 'pending'
                    CHECK (status IN ('pending', 'pending (item modified)', 'processed',
                                      'delivered', 'cancelled', 'exchange requested',
                                      'return requested')),
    cancel_reason   TEXT CHECK (cancel_reason IS NULL OR
                                cancel_reason IN ('no longer needed', 'ordered by mistake')),
    -- Exchange fields
    exchange_items              TEXT,  -- JSON array of item_ids
    exchange_new_items          TEXT,  -- JSON array of new item_ids
    exchange_payment_method_id  TEXT,
    exchange_price_difference   REAL,
    -- Return fields
    return_items                TEXT,  -- JSON array of item_ids
    return_payment_method_id    TEXT,
    created_at      TEXT DEFAULT (datetime('now'))
);

CREATE INDEX IF NOT EXISTS idx_orders_user ON orders(user_id);
CREATE INDEX IF NOT EXISTS idx_orders_status ON orders(status);

-- ============================================================================
-- ORDER ITEMS (items within an order)
-- ============================================================================
CREATE TABLE IF NOT EXISTS order_items (
    id              INTEGER PRIMARY KEY AUTOINCREMENT,
    order_id        TEXT NOT NULL REFERENCES orders(order_id) ON DELETE CASCADE,
    product_id      TEXT NOT NULL,
    item_id         TEXT NOT NULL,  -- variant/item id
    name            TEXT NOT NULL,  -- product name at time of purchase
    price           REAL NOT NULL,  -- price at time of purchase
    options         TEXT NOT NULL   -- JSON: options at time of purchase
);

CREATE INDEX IF NOT EXISTS idx_order_items_order ON order_items(order_id);
CREATE INDEX IF NOT EXISTS idx_order_items_item ON order_items(item_id);

-- ============================================================================
-- ORDER FULFILLMENTS (tracking info for shipped items)
-- ============================================================================
CREATE TABLE IF NOT EXISTS order_fulfillments (
    id              INTEGER PRIMARY KEY AUTOINCREMENT,
    order_id        TEXT NOT NULL REFERENCES orders(order_id) ON DELETE CASCADE,
    tracking_ids    TEXT NOT NULL,  -- JSON array of tracking IDs
    item_ids        TEXT NOT NULL,  -- JSON array of item IDs in this shipment
    created_at      TEXT DEFAULT (datetime('now'))
);

CREATE INDEX IF NOT EXISTS idx_order_fulfillments_order ON order_fulfillments(order_id);

-- ============================================================================
-- PAYMENT HISTORY (payments/refunds for orders)
-- ============================================================================
CREATE TABLE IF NOT EXISTS payment_history (
    id                  INTEGER PRIMARY KEY AUTOINCREMENT,
    order_id            TEXT NOT NULL REFERENCES orders(order_id) ON DELETE CASCADE,
    transaction_type    TEXT NOT NULL CHECK (transaction_type IN ('payment', 'refund')),
    amount              REAL NOT NULL,
    payment_method_id   TEXT NOT NULL,
    created_at          TEXT DEFAULT (datetime('now'))
);

CREATE INDEX IF NOT EXISTS idx_payment_history_order ON payment_history(order_id);
