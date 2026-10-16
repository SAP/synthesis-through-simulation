"""Seed reference data for the Online Discussion Forum environment."""

# (user_id, username, email, joined_date, reputation, role)
USERS = [
    ("USR001", "admin_alex",   "admin.alex@forum.com",   "2020-01-01", 5000, "admin"),
    ("USR002", "mod_morgan",   "mod.morgan@forum.com",   "2020-03-15", 3200, "moderator"),
    ("USR003", "mod_taylor",   "mod.taylor@forum.com",   "2020-06-20", 2800, "moderator"),
    ("USR004", "alice_dev",    "alice.dev@mail.com",      "2021-01-10", 1200, "member"),
    ("USR005", "bob_science",  "bob.science@mail.com",    "2021-04-22", 880,  "member"),
    ("USR006", "carol_reads",  "carol.reads@mail.com",    "2021-07-05", 650,  "member"),
    ("USR007", "dave_codes",   "dave.codes@mail.com",     "2022-02-14", 420,  "member"),
    ("USR008", "eve_travel",   "eve.travel@mail.com",     "2022-05-30", 310,  "member"),
    ("USR009", "frank_photo",  "frank.photo@mail.com",    "2022-09-11", 190,  "member"),
    ("USR010", "grace_music",  "grace.music@mail.com",    "2023-01-28", 75,   "member"),
]

# (category_id, name, description, parent_category_id)
CATEGORIES = [
    ("CAT001", "Technology",    "Discussions about software, hardware, and the digital world", None),
    ("CAT002", "Science",       "Physics, biology, chemistry, and scientific discoveries",    None),
    ("CAT003", "Arts & Culture","Literature, music, film, visual arts, and creative topics",  None),
    ("CAT004", "General",       "Off-topic chat and general discussions",                      None),
    ("CAT005", "Programming",   "Code, algorithms, and development tools",                     "CAT001"),
    ("CAT006", "Gadgets",       "Reviews and discussions of consumer electronics",             "CAT001"),
]

# (tag_id, name, description, is_approved)
TAGS = [
    ("TAG001", "python",        "Python programming language",     1),
    ("TAG002", "javascript",    "JavaScript and web development",  1),
    ("TAG003", "machine-learning", "ML, AI, and data science",     1),
    ("TAG004", "biology",       "Biological sciences",             1),
    ("TAG005", "space",         "Astronomy and space exploration", 1),
    ("TAG006", "books",         "Book recommendations and reviews",1),
    ("TAG007", "music",         "Music genres and recommendations",1),
    ("TAG008", "photography",   "Photography tips and showcase",   1),
    ("TAG009", "travel",        "Travel guides and experiences",   1),
    ("TAG010", "gaming",        "Video games and gaming culture",  1),
]
