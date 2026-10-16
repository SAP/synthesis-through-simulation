# (product_id, name)
PRODUCTS = [
    ("prod_laptop_001", "Laptop Pro 15"),
    ("prod_phone_001", "Smartphone Ultra X"),
    ("prod_tablet_001", "Tablet Air 10"),
    ("prod_headphones_001", "Wireless Headphones Pro"),
    ("prod_monitor_001", "4K Monitor 27"),
    ("prod_keyboard_001", "Mechanical Keyboard TKL"),
    ("prod_charger_001", "Portable Charger 20000mAh"),
    ("prod_hub_001", "USB-C 7-in-1 Hub"),
]

# (item_id, product_id, options_json, available, price)
VARIANTS = [
    # Laptop Pro 15
    ("item_laptop_s256", "prod_laptop_001", '{"color": "silver", "storage": "256GB"}', 1, 899.99),
    ("item_laptop_s512", "prod_laptop_001", '{"color": "silver", "storage": "512GB"}', 1, 1099.99),
    ("item_laptop_g256", "prod_laptop_001", '{"color": "space gray", "storage": "256GB"}', 1, 899.99),
    ("item_laptop_g512", "prod_laptop_001", '{"color": "space gray", "storage": "512GB"}', 0, 1099.99),
    # Smartphone Ultra X
    ("item_phone_b128", "prod_phone_001", '{"color": "black", "storage": "128GB"}', 1, 699.99),
    ("item_phone_b256", "prod_phone_001", '{"color": "black", "storage": "256GB"}', 1, 799.99),
    ("item_phone_w128", "prod_phone_001", '{"color": "white", "storage": "128GB"}', 1, 699.99),
    ("item_phone_w256", "prod_phone_001", '{"color": "white", "storage": "256GB"}', 1, 799.99),
    # Tablet Air 10
    ("item_tablet_w64", "prod_tablet_001", '{"color": "white", "storage": "64GB"}', 1, 449.99),
    ("item_tablet_w128", "prod_tablet_001", '{"color": "white", "storage": "128GB"}', 1, 549.99),
    ("item_tablet_g64", "prod_tablet_001", '{"color": "graphite", "storage": "64GB"}', 1, 449.99),
    # Wireless Headphones Pro
    ("item_hp_black", "prod_headphones_001", '{"color": "black"}', 1, 249.99),
    ("item_hp_white", "prod_headphones_001", '{"color": "white"}', 1, 249.99),
    ("item_hp_silver", "prod_headphones_001", '{"color": "silver"}', 0, 249.99),
    # 4K Monitor 27
    ("item_mon_black", "prod_monitor_001", '{"color": "black"}', 1, 399.99),
    ("item_mon_white", "prod_monitor_001", '{"color": "white"}', 1, 399.99),
    # Mechanical Keyboard TKL
    ("item_kb_black_br", "prod_keyboard_001", '{"color": "black", "switch": "brown"}', 1, 129.99),
    ("item_kb_white_br", "prod_keyboard_001", '{"color": "white", "switch": "brown"}', 1, 129.99),
    ("item_kb_silver_rd", "prod_keyboard_001", '{"color": "silver", "switch": "red"}', 1, 119.99),
    # Portable Charger 20000mAh
    ("item_chg_black", "prod_charger_001", '{"color": "black"}', 1, 49.99),
    ("item_chg_white", "prod_charger_001", '{"color": "white"}', 1, 49.99),
    # USB-C 7-in-1 Hub
    ("item_hub_gray", "prod_hub_001", '{"color": "gray"}', 1, 59.99),
    ("item_hub_silver", "prod_hub_001", '{"color": "silver"}', 1, 59.99),
]

# (user_id, first_name, last_name, email, address1, address2, city, state, country, zip)
USERS = [
    ("user_alice_001", "Alice", "Johnson", "alice.johnson@email.com",
     "123 Oak Street", None, "Springfield", "IL", "US", "62701"),
    ("user_bob_002", "Bob", "Martinez", "bob.martinez@email.com",
     "456 Elm Ave", "Apt 2B", "Chicago", "IL", "US", "60601"),
    ("user_carol_003", "Carol", "Wang", "carol.wang@email.com",
     "789 Maple Rd", None, "Austin", "TX", "US", "73301"),
    ("user_david_004", "David", "Smith", "david.smith@email.com",
     "321 Pine St", "Suite 100", "Seattle", "WA", "US", "98101"),
    ("user_emma_005", "Emma", "Davis", "emma.davis@email.com",
     "654 Cedar Blvd", None, "Denver", "CO", "US", "80201"),
    ("user_frank_006", "Frank", "Lee", "frank.lee@email.com",
     "987 Birch Way", None, "Miami", "FL", "US", "33101"),
    ("user_grace_007", "Grace", "Brown", "grace.brown@email.com",
     "147 Walnut Dr", "Apt 4A", "Portland", "OR", "US", "97201"),
    ("user_henry_008", "Henry", "Wilson", "henry.wilson@email.com",
     "258 Spruce Ln", None, "Nashville", "TN", "US", "37201"),
    ("user_iris_009", "Iris", "Taylor", "iris.taylor@email.com",
     "369 Aspen Ct", None, "Phoenix", "AZ", "US", "85001"),
    ("user_jack_010", "Jack", "Anderson", "jack.anderson@email.com",
     "741 Willow St", "Unit 7", "Boston", "MA", "US", "02101"),
]

# (payment_method_id, user_id, source, brand, last_four, balance)
PAYMENT_METHODS = [
    ("cc_alice_001",  "user_alice_001", "credit_card", "visa",       "4532", None),
    ("gc_alice_001",  "user_alice_001", "gift_card",   None,          None,  150.00),
    ("cc_bob_001",    "user_bob_002",   "credit_card", "mastercard", "8821", None),
    ("pp_carol_001",  "user_carol_003", "paypal",      None,          None,  None),
    ("cc_david_001",  "user_david_004", "credit_card", "visa",       "1234", None),
    ("gc_david_001",  "user_david_004", "gift_card",   None,          None,  50.00),
    ("cc_emma_001",   "user_emma_005",  "credit_card", "mastercard", "5678", None),
    ("pp_frank_001",  "user_frank_006", "paypal",      None,          None,  None),
    ("gc_frank_001",  "user_frank_006", "gift_card",   None,          None,  75.00),
    ("cc_grace_001",  "user_grace_007", "credit_card", "visa",       "9012", None),
    ("cc_henry_001",  "user_henry_008", "credit_card", "amex",       "3456", None),
    ("cc_iris_001",   "user_iris_009",  "credit_card", "mastercard", "7890", None),
    ("gc_iris_001",   "user_iris_009",  "gift_card",   None,          None,  200.00),
    ("cc_jack_001",   "user_jack_010",  "credit_card", "visa",       "2345", None),
]

# (order_id, user_id, address1, address2, city, state, country, zip, status,
#  cancel_reason, exchange_items, exchange_new_items, exchange_payment_method_id,
#  exchange_price_difference, return_items, return_payment_method_id)
ORDERS = [
    ("#W0000001", "user_alice_001",
     "123 Oak Street", None, "Springfield", "IL", "US", "62701",
     "pending", None, None, None, None, None, None, None),
    ("#W0000002", "user_bob_002",
     "456 Elm Ave", "Apt 2B", "Chicago", "IL", "US", "60601",
     "pending (item modified)", None, None, None, None, None, None, None),
    ("#W0000003", "user_carol_003",
     "789 Maple Rd", None, "Austin", "TX", "US", "73301",
     "processed", None, None, None, None, None, None, None),
    ("#W0000004", "user_david_004",
     "321 Pine St", "Suite 100", "Seattle", "WA", "US", "98101",
     "delivered", None, None, None, None, None, None, None),
    ("#W0000005", "user_emma_005",
     "654 Cedar Blvd", None, "Denver", "CO", "US", "80201",
     "delivered", None, None, None, None, None, None, None),
    ("#W0000006", "user_frank_006",
     "987 Birch Way", None, "Miami", "FL", "US", "33101",
     "cancelled", "no longer needed", None, None, None, None, None, None),
    ("#W0000007", "user_grace_007",
     "147 Walnut Dr", "Apt 4A", "Portland", "OR", "US", "97201",
     "exchange requested", None,
     '["item_phone_w256"]', '["item_phone_b256"]', "cc_grace_001", 0.00,
     None, None),
    ("#W0000008", "user_henry_008",
     "258 Spruce Ln", None, "Nashville", "TN", "US", "37201",
     "return requested", None,
     None, None, None, None,
     '["item_mon_black"]', "cc_henry_001"),
    ("#W0000009", "user_iris_009",
     "369 Aspen Ct", None, "Phoenix", "AZ", "US", "85001",
     "delivered", None, None, None, None, None, None, None),
    ("#W0000010", "user_jack_010",
     "741 Willow St", "Unit 7", "Boston", "MA", "US", "02101",
     "pending", None, None, None, None, None, None, None),
]

# (order_id, product_id, item_id, name, price, options_json)
ORDER_ITEMS = [
    ("#W0000001", "prod_laptop_001",     "item_laptop_s256",  "Laptop Pro 15",              899.99,  '{"color": "silver", "storage": "256GB"}'),
    ("#W0000002", "prod_phone_001",      "item_phone_b128",   "Smartphone Ultra X",         699.99,  '{"color": "black", "storage": "128GB"}'),
    ("#W0000003", "prod_headphones_001", "item_hp_black",     "Wireless Headphones Pro",    249.99,  '{"color": "black"}'),
    ("#W0000003", "prod_charger_001",    "item_chg_black",    "Portable Charger 20000mAh",   49.99,  '{"color": "black"}'),
    ("#W0000004", "prod_laptop_001",     "item_laptop_g512",  "Laptop Pro 15",             1099.99,  '{"color": "space gray", "storage": "512GB"}'),
    ("#W0000005", "prod_tablet_001",     "item_tablet_w64",   "Tablet Air 10",              449.99,  '{"color": "white", "storage": "64GB"}'),
    ("#W0000006", "prod_keyboard_001",   "item_kb_black_br",  "Mechanical Keyboard TKL",    129.99,  '{"color": "black", "switch": "brown"}'),
    ("#W0000007", "prod_phone_001",      "item_phone_w256",   "Smartphone Ultra X",         799.99,  '{"color": "white", "storage": "256GB"}'),
    ("#W0000008", "prod_monitor_001",    "item_mon_black",    "4K Monitor 27",              399.99,  '{"color": "black"}'),
    ("#W0000009", "prod_headphones_001", "item_hp_white",     "Wireless Headphones Pro",    249.99,  '{"color": "white"}'),
    ("#W0000010", "prod_keyboard_001",   "item_kb_white_br",  "Mechanical Keyboard TKL",    129.99,  '{"color": "white", "switch": "brown"}'),
    ("#W0000010", "prod_charger_001",    "item_chg_white",    "Portable Charger 20000mAh",   49.99,  '{"color": "white"}'),
]

# (order_id, tracking_ids_json, item_ids_json)
ORDER_FULFILLMENTS = [
    ("#W0000003", '["TRK-20240301-001"]', '["item_hp_black", "item_chg_black"]'),
    ("#W0000004", '["TRK-20240302-001"]', '["item_laptop_g512"]'),
    ("#W0000005", '["TRK-20240303-001"]', '["item_tablet_w64"]'),
    ("#W0000007", '["TRK-20240304-001"]', '["item_phone_w256"]'),
    ("#W0000008", '["TRK-20240305-001"]', '["item_mon_black"]'),
    ("#W0000009", '["TRK-20240306-001"]', '["item_hp_white"]'),
]

# (order_id, transaction_type, amount, payment_method_id)
PAYMENT_HISTORY = [
    ("#W0000001", "payment",  899.99, "cc_alice_001"),
    ("#W0000002", "payment",  699.99, "cc_bob_001"),
    ("#W0000003", "payment",  299.98, "pp_carol_001"),
    ("#W0000004", "payment", 1099.99, "cc_david_001"),
    ("#W0000005", "payment",  449.99, "cc_emma_001"),
    ("#W0000006", "payment",  129.99, "pp_frank_001"),
    ("#W0000006", "refund",   129.99, "pp_frank_001"),
    ("#W0000007", "payment",  799.99, "cc_grace_001"),
    ("#W0000008", "payment",  399.99, "cc_henry_001"),
    ("#W0000009", "payment",  249.99, "cc_iris_001"),
    ("#W0000010", "payment",  179.98, "cc_jack_001"),
]
