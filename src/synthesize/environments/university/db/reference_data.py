"""Seed reference data for the University Course Registration environment."""

# (student_id, name, email, academic_program, enrollment_status, gpa, credits_completed)
STUDENTS = [
    ("STU001", "Alice Park",       "alice.park@uni.edu",       "Computer Science",       "active", 3.8, 90),
    ("STU002", "Ben Torres",       "ben.torres@uni.edu",       "Electrical Engineering", "active", 3.2, 60),
    ("STU003", "Chloe Martin",     "chloe.martin@uni.edu",     "Biology",                "active", 3.6, 75),
    ("STU004", "Daniel Kim",       "daniel.kim@uni.edu",       "Mathematics",            "active", 3.9, 105),
    ("STU005", "Elena Vasquez",    "elena.vasquez@uni.edu",    "Computer Science",       "active", 2.9, 45),
    ("STU006", "Felix Nguyen",     "felix.nguyen@uni.edu",     "Physics",                "active", 3.5, 80),
    ("STU007", "Gina Patel",       "gina.patel@uni.edu",       "Chemistry",              "active", 3.7, 90),
    ("STU008", "Hassan Ali",       "hassan.ali@uni.edu",       "Mechanical Engineering", "active", 3.1, 55),
    ("STU009", "Isabella Chen",    "isabella.chen@uni.edu",    "Economics",              "active", 3.4, 70),
    ("STU010", "Jack Brown",       "jack.brown@uni.edu",       "History",                "inactive", 2.5, 30),
    ("STU011", "Katie Lopez",      "katie.lopez@uni.edu",      "Psychology",             "active", 3.6, 85),
    ("STU012", "Liam Johnson",     "liam.johnson@uni.edu",     "Business Administration","active", 3.3, 65),
    ("STU013", "Maya Singh",       "maya.singh@uni.edu",       "Computer Science",       "active", 3.8, 100),
    ("STU014", "Noah Williams",    "noah.williams@uni.edu",    "Environmental Science",  "active", 3.0, 50),
    ("STU015", "Olivia Davis",     "olivia.davis@uni.edu",     "Nursing",                "active", 3.7, 95),
    ("STU016", "Paul Rodriguez",   "paul.rodriguez@uni.edu",   "Electrical Engineering", "active", 3.2, 70),
    ("STU017", "Quinn Wilson",     "quinn.wilson@uni.edu",     "Mathematics",            "active", 3.5, 80),
    ("STU018", "Rachel Thompson",  "rachel.thompson@uni.edu",  "Biology",                "graduated", 3.9, 120),
    ("STU019", "Sam Garcia",       "sam.garcia@uni.edu",       "Psychology",             "active", 2.8, 40),
    ("STU020", "Tina Lee",         "tina.lee@uni.edu",         "Business Administration","active", 3.4, 60),
]

# (course_id, course_code, title, instructor, department, capacity, current_enrollment, credits, is_open)
COURSES = [
    ("CRS001", "CS101",  "Introduction to Programming",       "Prof. Adams",    "Computer Science",       30, 28, 3, 1),
    ("CRS002", "CS201",  "Data Structures and Algorithms",    "Prof. Baker",    "Computer Science",       25, 25, 3, 1),
    ("CRS003", "CS301",  "Operating Systems",                 "Prof. Clark",    "Computer Science",       20, 15, 3, 1),
    ("CRS004", "MATH101","Calculus I",                        "Prof. Davis",    "Mathematics",            35, 34, 4, 1),
    ("CRS005", "MATH201","Linear Algebra",                    "Prof. Evans",    "Mathematics",            30, 20, 3, 1),
    ("CRS006", "PHY101", "General Physics I",                 "Prof. Foster",   "Physics",                40, 38, 4, 1),
    ("CRS007", "BIO101", "Introduction to Biology",           "Prof. Green",    "Biology",                35, 30, 3, 1),
    ("CRS008", "CHEM101","General Chemistry",                 "Prof. Hall",     "Chemistry",              30, 30, 4, 1),
    ("CRS009", "ECON101","Principles of Economics",           "Prof. Irwin",    "Economics",              50, 45, 3, 1),
    ("CRS010", "PSYCH101","Introduction to Psychology",       "Prof. Jones",    "Psychology",             45, 44, 3, 1),
    ("CRS011", "ENG101", "Technical Writing",                 "Prof. King",     "English",                25, 10, 3, 1),
    ("CRS012", "HIST201","Modern World History",              "Prof. Lewis",    "History",                30, 22, 3, 1),
    ("CRS013", "BUS301", "Business Strategy",                 "Prof. Moore",    "Business",               25, 25, 3, 1),
    ("CRS014", "EE201",  "Circuit Analysis",                  "Prof. Nelson",   "Electrical Engineering", 20, 18, 4, 1),
    ("CRS015", "ENV101", "Introduction to Environmental Science", "Prof. Owen", "Environmental Science",  30, 12, 3, 1),
]
