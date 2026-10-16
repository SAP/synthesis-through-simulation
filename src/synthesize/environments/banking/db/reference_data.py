"""Seed reference data for the Retail Banking environment."""

# (customer_id, name, email, phone, address, id_type, id_number)
CUSTOMERS = [
    ("CUST001", "Alice Johnson", "alice.johnson@email.com", "555-0101", "123 Maple St, Springfield", "driver_license", "DL-AJ-001"),
    ("CUST002", "Bob Martinez", "bob.martinez@email.com", "555-0102", "456 Oak Ave, Shelbyville", "passport", "PP-BM-002"),
    ("CUST003", "Carol White", "carol.white@email.com", "555-0103", "789 Pine Rd, Capital City", "national_id", "NI-CW-003"),
    ("CUST004", "David Lee", "david.lee@email.com", "555-0104", "321 Elm St, Springfield", "driver_license", "DL-DL-004"),
    ("CUST005", "Emma Davis", "emma.davis@email.com", "555-0105", "654 Cedar Ln, Shelbyville", "passport", "PP-ED-005"),
    ("CUST006", "Frank Wilson", "frank.wilson@email.com", "555-0106", "987 Birch Blvd, Capital City", "national_id", "NI-FW-006"),
    ("CUST007", "Grace Brown", "grace.brown@email.com", "555-0107", "147 Walnut Way, Springfield", "driver_license", "DL-GB-007"),
    ("CUST008", "Henry Taylor", "henry.taylor@email.com", "555-0108", "258 Spruce Ct, Shelbyville", "passport", "PP-HT-008"),
    ("CUST009", "Iris Anderson", "iris.anderson@email.com", "555-0109", "369 Aspen Dr, Capital City", "national_id", "NI-IA-009"),
    ("CUST010", "James Thomas", "james.thomas@email.com", "555-0110", "741 Poplar Pl, Springfield", "driver_license", "DL-JT-010"),
    ("CUST011", "Karen Jackson", "karen.jackson@email.com", "555-0111", "852 Willow Way, Shelbyville", "passport", "PP-KJ-011"),
    ("CUST012", "Leo Harris", "leo.harris@email.com", "555-0112", "963 Redwood Rd, Capital City", "national_id", "NI-LH-012"),
]

# (account_id, customer_id, account_type, balance, currency, status, overdraft_allowed, opening_date)
ACCOUNTS = [
    ("ACC001", "CUST001", "checking", 2450.75, "USD", "active", 1, "2021-03-15"),
    ("ACC002", "CUST001", "savings",  8200.00, "USD", "active", 0, "2021-03-15"),
    ("ACC003", "CUST002", "checking", 1100.50, "USD", "active", 1, "2020-07-22"),
    ("ACC004", "CUST002", "savings",  15000.00, "USD", "active", 0, "2020-07-22"),
    ("ACC005", "CUST003", "checking", 3300.25, "USD", "active", 0, "2022-01-10"),
    ("ACC006", "CUST004", "savings",  22000.00, "USD", "active", 0, "2019-11-05"),
    ("ACC007", "CUST004", "loan",     -5000.00, "USD", "active", 0, "2023-02-28"),
    ("ACC008", "CUST005", "checking", 850.00,  "USD", "active", 1, "2021-09-14"),
    ("ACC009", "CUST005", "savings",  4500.00,  "USD", "active", 0, "2021-09-14"),
    ("ACC010", "CUST006", "checking", 12000.00, "USD", "active", 0, "2018-06-30"),
    ("ACC011", "CUST007", "checking", 0.00,    "USD", "frozen", 0, "2022-04-01"),
    ("ACC012", "CUST007", "savings",  6750.50,  "USD", "active", 0, "2022-04-01"),
    ("ACC013", "CUST008", "checking", 2200.00,  "USD", "active", 1, "2020-12-15"),
    ("ACC014", "CUST009", "savings",  9800.00,  "USD", "active", 0, "2023-05-20"),
    ("ACC015", "CUST010", "checking", 1750.00,  "USD", "active", 0, "2021-08-08"),
    ("ACC016", "CUST010", "loan",     -12000.00, "USD", "active", 0, "2022-10-01"),
    ("ACC017", "CUST011", "checking", 3400.00,  "USD", "active", 1, "2019-03-17"),
    ("ACC018", "CUST011", "savings",  18500.00, "USD", "active", 0, "2019-03-17"),
    ("ACC019", "CUST012", "checking", 500.00,   "USD", "active", 1, "2023-07-04"),
    ("ACC020", "CUST012", "savings",  2000.00,  "USD", "active", 0, "2023-07-04"),
]
