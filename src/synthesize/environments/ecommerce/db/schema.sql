-- E-commerce Order Management System schema

CREATE TABLE IF NOT EXISTS customer (
    customer_id  TEXT PRIMARY KEY,
    name         TEXT NOT NULL,
    email        TEXT NOT NULL UNIQUE,
    phone        TEXT,
    address      TEXT,
    is_active    INTEGER NOT NULL DEFAULT 1,
    created_date TEXT NOT NULL
);

CREATE TABLE IF NOT EXISTS product (
    product_id  TEXT PRIMARY KEY,
    name        TEXT NOT NULL,
    category    TEXT NOT NULL,
    price       REAL NOT NULL,
    stock_qty   INTEGER NOT NULL DEFAULT 0,
    description TEXT,
    is_active   INTEGER NOT NULL DEFAULT 1
);

CREATE TABLE IF NOT EXISTS shop_order (
    order_id         TEXT PRIMARY KEY,
    customer_id      TEXT NOT NULL REFERENCES customer(customer_id),
    status           TEXT NOT NULL DEFAULT 'pending',
    -- 'pending', 'confirmed', 'shipped', 'delivered', 'cancelled'
    total_amount     REAL NOT NULL DEFAULT 0.0,
    shipping_address TEXT NOT NULL,
    created_date     TEXT NOT NULL,
    updated_date     TEXT NOT NULL
);

CREATE TABLE IF NOT EXISTS order_item (
    order_item_id TEXT PRIMARY KEY,
    order_id      TEXT NOT NULL REFERENCES shop_order(order_id),
    product_id    TEXT NOT NULL REFERENCES product(product_id),
    quantity      INTEGER NOT NULL,
    unit_price    REAL NOT NULL
);

CREATE INDEX IF NOT EXISTS idx_order_customer  ON shop_order(customer_id);
CREATE INDEX IF NOT EXISTS idx_order_item_order ON order_item(order_id);
