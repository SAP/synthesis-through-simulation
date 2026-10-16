"""Seed reference data for the E-commerce Order Management environment."""

# (customer_id, name, email, phone, address)
CUSTOMERS = [
    ("ECUST001", "Alice Morgan",  "alice.morgan@shop.com",  "555-3001", "10 Main St, Portland, OR"),
    ("ECUST002", "Brian Scott",   "brian.scott@shop.com",   "555-3002", "22 Oak Ave, Seattle, WA"),
    ("ECUST003", "Clara Diaz",    "clara.diaz@shop.com",    "555-3003", "35 Pine Rd, Denver, CO"),
    ("ECUST004", "Derek Young",   "derek.young@shop.com",   "555-3004", "48 Elm St, Austin, TX"),
    ("ECUST005", "Elena Ford",    "elena.ford@shop.com",    "555-3005", "57 Cedar Ln, Miami, FL"),
    ("ECUST006", "Fred Hill",     "fred.hill@shop.com",     "555-3006", "61 Maple Blvd, Chicago, IL"),
    ("ECUST007", "Gina Rivers",   "gina.rivers@shop.com",   "555-3007", "74 Walnut Way, Boston, MA"),
    ("ECUST008", "Hugo Stone",    "hugo.stone@shop.com",    "555-3008", "89 Spruce Ct, Phoenix, AZ"),
    ("ECUST009", "Isla Carter",   "isla.carter@shop.com",   "555-3009", "93 Birch Dr, Nashville, TN"),
    ("ECUST010", "Jake Turner",   "jake.turner@shop.com",   "555-3010", "102 Ash Pl, Minneapolis, MN"),
    ("ECUST011", "Karen Bell",    "karen.bell@shop.com",    "555-3011", "115 Poplar St, Atlanta, GA"),
    ("ECUST012", "Luis Reyes",    "luis.reyes@shop.com",    "555-3012", "128 Willow Rd, Las Vegas, NV"),
]

# (product_id, name, category, price, stock_qty, description)
PRODUCTS = [
    ("PROD001", "Wireless Headphones",     "Electronics",  89.99, 150, "Over-ear Bluetooth headphones, 30hr battery"),
    ("PROD002", "Running Shoes",           "Footwear",     65.00, 200, "Lightweight mesh running shoes, various sizes"),
    ("PROD003", "Coffee Maker",            "Appliances",   49.99,  80, "12-cup programmable drip coffee maker"),
    ("PROD004", "Yoga Mat",                "Sports",       25.00, 300, "Non-slip 6mm thick yoga mat, 183x61cm"),
    ("PROD005", "Backpack",                "Bags",         45.00, 120, "30L waterproof hiking backpack"),
    ("PROD006", "Stainless Steel Bottle",  "Kitchen",      22.50, 400, "Insulated 750ml water bottle"),
    ("PROD007", "Desk Lamp",               "Office",       35.00,  90, "LED desk lamp with USB charging port"),
    ("PROD008", "Bluetooth Speaker",       "Electronics",  59.99, 110, "Portable waterproof speaker, 360 sound"),
    ("PROD009", "Novel - The Lost Garden", "Books",        14.99, 500, "Bestselling fiction novel"),
    ("PROD010", "Mechanical Keyboard",     "Electronics", 119.00,  60, "Tenkeyless, blue switches"),
    ("PROD011", "Sunglasses",              "Accessories",  38.00, 180, "UV400 polarized sunglasses"),
    ("PROD012", "Protein Powder",          "Health",       42.00, 250, "Whey protein blend, chocolate, 1kg"),
    ("PROD013", "Notebook Set",            "Stationery",   12.00, 600, "Set of 3 ruled notebooks, A5"),
    ("PROD014", "Smart Watch",             "Electronics", 199.00,  40, "Fitness tracking smartwatch, 5ATM"),
    ("PROD015", "Cast Iron Skillet",       "Kitchen",      55.00,  70, "10-inch pre-seasoned cast iron pan"),
    ("PROD016", "Resistance Bands",        "Sports",       18.50, 350, "Set of 5 resistance bands, various strengths"),
    ("PROD017", "USB-C Hub",               "Electronics",  34.99,  95, "7-in-1 USB-C hub with HDMI, USB 3.0"),
    ("PROD018", "Travel Pillow",           "Travel",       19.00, 220, "Memory foam U-shaped neck pillow"),
    ("PROD019", "Cookbooks Collection",    "Books",        29.99, 130, "Set of 2 international cuisine cookbooks"),
    ("PROD020", "Desk Organizer",          "Office",       27.00,  85, "Bamboo desktop organizer with 5 compartments"),
]
