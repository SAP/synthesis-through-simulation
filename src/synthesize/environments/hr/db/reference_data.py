"""
Master / reference data for the HR mock system.

These are the static foundation objects that every experiment run starts from.
generate_comprehensive_data.py imports these to build full demo datasets.
setup.py inserts them directly to create a clean baseline DB.
"""

# ── Org structure ─────────────────────────────────────────────────────────────

COMPANIES = [
    {"code": "ACME_US", "name": "ACME Corporation USA", "country": "USA"},
    {"code": "ACME_UK", "name": "ACME Limited UK", "country": "GBR"},
    {"code": "ACME_DE", "name": "ACME GmbH", "country": "DEU"},
]

LOCATIONS = [
    {
        "code": "LOC_NYC",
        "name": "New York City",
        "country": "USA",
        "city": "New York",
        "state": "NY",
    },
    {
        "code": "LOC_SF",
        "name": "San Francisco",
        "country": "USA",
        "city": "San Francisco",
        "state": "CA",
    },
    {"code": "LOC_CHI", "name": "Chicago", "country": "USA", "city": "Chicago", "state": "IL"},
    {"code": "LOC_LON", "name": "London", "country": "GBR", "city": "London", "state": ""},
    {"code": "LOC_BER", "name": "Berlin", "country": "DEU", "city": "Berlin", "state": ""},
    {"code": "LOC_AUS", "name": "Austin", "country": "USA", "city": "Austin", "state": "TX"},
]

DIVISIONS = [
    {"code": "DIV_ENG", "name": "Engineering"},
    {"code": "DIV_SALES", "name": "Sales & Marketing"},
    {"code": "DIV_OPS", "name": "Operations"},
    {"code": "DIV_FIN", "name": "Finance & Administration"},
]

DEPARTMENTS = [
    {"code": "DEPT_IT", "name": "Information Technology", "division": "DIV_ENG"},
    {"code": "DEPT_PROD", "name": "Product Management", "division": "DIV_ENG"},
    {"code": "DEPT_ENG", "name": "Software Engineering", "division": "DIV_ENG"},
    {"code": "DEPT_SALES", "name": "Sales", "division": "DIV_SALES"},
    {"code": "DEPT_MKT", "name": "Marketing", "division": "DIV_SALES"},
    {"code": "DEPT_HR", "name": "Human Resources", "division": "DIV_OPS"},
    {"code": "DEPT_OPS", "name": "Operations", "division": "DIV_OPS"},
    {"code": "DEPT_FIN", "name": "Finance", "division": "DIV_FIN"},
    {"code": "DEPT_LEGAL", "name": "Legal", "division": "DIV_FIN"},
]

BUSINESS_UNITS = [
    {"code": "BU_CORP", "name": "Corporate"},
    {"code": "BU_PROD", "name": "Product Development"},
    {"code": "BU_CUST", "name": "Customer Success"},
]

COST_CENTERS = [
    {"code": "CC_1000", "name": "Engineering - Core"},
    {"code": "CC_1100", "name": "Engineering - Platform"},
    {"code": "CC_2000", "name": "Sales - North America"},
    {"code": "CC_2100", "name": "Sales - International"},
    {"code": "CC_3000", "name": "Marketing"},
    {"code": "CC_4000", "name": "Finance & Admin"},
    {"code": "CC_5000", "name": "HR & Operations"},
]

# ── Jobs & compensation ───────────────────────────────────────────────────────

JOB_CODES = [
    {
        "code": "JOB_CEO",
        "title": "Chief Executive Officer",
        "level": "Executive",
        "family": "Leadership",
    },
    {
        "code": "JOB_CTO",
        "title": "Chief Technology Officer",
        "level": "Executive",
        "family": "Leadership",
    },
    {
        "code": "JOB_CFO",
        "title": "Chief Financial Officer",
        "level": "Executive",
        "family": "Leadership",
    },
    {
        "code": "JOB_VP_ENG",
        "title": "VP of Engineering",
        "level": "Senior Leadership",
        "family": "Leadership",
    },
    {
        "code": "JOB_VP_SALES",
        "title": "VP of Sales",
        "level": "Senior Leadership",
        "family": "Leadership",
    },
    {
        "code": "JOB_DIR_ENG",
        "title": "Director of Engineering",
        "level": "Management",
        "family": "Engineering",
    },
    {
        "code": "JOB_ENG_MGR",
        "title": "Engineering Manager",
        "level": "Management",
        "family": "Engineering",
    },
    {
        "code": "JOB_SR_ENG",
        "title": "Senior Software Engineer",
        "level": "Senior IC",
        "family": "Engineering",
    },
    {"code": "JOB_ENG", "title": "Software Engineer", "level": "Mid IC", "family": "Engineering"},
    {
        "code": "JOB_JR_ENG",
        "title": "Junior Software Engineer",
        "level": "Junior IC",
        "family": "Engineering",
    },
    {"code": "JOB_PROD_MGR", "title": "Product Manager", "level": "Mid IC", "family": "Product"},
    {
        "code": "JOB_SR_PROD",
        "title": "Senior Product Manager",
        "level": "Senior IC",
        "family": "Product",
    },
    {
        "code": "JOB_SALES_REP",
        "title": "Sales Representative",
        "level": "Mid IC",
        "family": "Sales",
    },
    {
        "code": "JOB_SR_SALES",
        "title": "Senior Sales Executive",
        "level": "Senior IC",
        "family": "Sales",
    },
    {"code": "JOB_SALES_MGR", "title": "Sales Manager", "level": "Management", "family": "Sales"},
    {
        "code": "JOB_MKT_MGR",
        "title": "Marketing Manager",
        "level": "Management",
        "family": "Marketing",
    },
    {
        "code": "JOB_MKT_SPEC",
        "title": "Marketing Specialist",
        "level": "Mid IC",
        "family": "Marketing",
    },
    {"code": "JOB_FIN_MGR", "title": "Finance Manager", "level": "Management", "family": "Finance"},
    {"code": "JOB_ACCOUNTANT", "title": "Accountant", "level": "Mid IC", "family": "Finance"},
    {"code": "JOB_HR_MGR", "title": "HR Manager", "level": "Management", "family": "HR"},
    {"code": "JOB_HR_BP", "title": "HR Business Partner", "level": "Mid IC", "family": "HR"},
    {"code": "JOB_RECRUITER", "title": "Recruiter", "level": "Mid IC", "family": "HR"},
]

PAY_GRADES = [
    {"code": "PG_01", "name": "Executive", "min_salary": 250000, "max_salary": 500000},
    {"code": "PG_02", "name": "Senior Leadership", "min_salary": 180000, "max_salary": 300000},
    {"code": "PG_03", "name": "Management", "min_salary": 120000, "max_salary": 200000},
    {
        "code": "PG_04",
        "name": "Senior Individual Contributor",
        "min_salary": 100000,
        "max_salary": 160000,
    },
    {"code": "PG_05", "name": "Mid-Level", "min_salary": 70000, "max_salary": 110000},
    {"code": "PG_06", "name": "Junior", "min_salary": 50000, "max_salary": 75000},
]

PAY_COMPONENTS = [
    {"code": "BASE", "name": "Base Salary", "type": "Recurring"},
    {"code": "BONUS", "name": "Annual Bonus", "type": "Non-Recurring"},
    {"code": "COMMISSION", "name": "Sales Commission", "type": "Recurring"},
    {"code": "STOCK", "name": "Stock Grant", "type": "Non-Recurring"},
    {"code": "CAR_ALLOW", "name": "Car Allowance", "type": "Recurring"},
]

EVENT_REASONS = [
    {"code": "NEW_HIRE", "name": "New Hire", "event_type": "Hire"},
    {"code": "PROMOTION", "name": "Promotion", "event_type": "Job Change"},
    {"code": "TRANSFER", "name": "Transfer", "event_type": "Job Change"},
    {"code": "SALARY_REVIEW", "name": "Salary Review", "event_type": "Compensation Change"},
    {"code": "RESIGNATION", "name": "Resignation", "event_type": "Termination"},
    {"code": "RETIREMENT", "name": "Retirement", "event_type": "Termination"},
]

# ── Reference / lookup tables ─────────────────────────────────────────────────

COMPETENCIES = [
    {"code": "COMP_LEAD", "name": "Leadership", "category": "Core"},
    {"code": "COMP_COMM", "name": "Communication", "category": "Core"},
    {"code": "COMP_PROB", "name": "Problem Solving", "category": "Core"},
    {"code": "COMP_TEAM", "name": "Teamwork", "category": "Core"},
    {"code": "COMP_TECH", "name": "Technical Expertise", "category": "Functional"},
    {"code": "COMP_CUST", "name": "Customer Focus", "category": "Functional"},
]

COUNTRIES = [
    {"code": "USA", "name": "United States"},
    {"code": "GBR", "name": "United Kingdom"},
    {"code": "DEU", "name": "Germany"},
    {"code": "CAN", "name": "Canada"},
    {"code": "IND", "name": "India"},
]

CURRENCIES = [
    {"code": "USD", "name": "US Dollar"},
    {"code": "GBP", "name": "British Pound"},
    {"code": "EUR", "name": "Euro"},
]

TIME_OFF_TYPES = [
    {"code": "VAC", "name": "Vacation", "accrual_rate": 15},
    {"code": "SICK", "name": "Sick Leave", "accrual_rate": 10},
    {"code": "PTO", "name": "Paid Time Off", "accrual_rate": 20},
    {"code": "BEREAVEMENT", "name": "Bereavement", "accrual_rate": 0},
]

BENEFIT_PLANS = [
    {"code": "HEALTH_BASIC", "name": "Basic Health Insurance", "type": "Medical"},
    {"code": "HEALTH_PREMIUM", "name": "Premium Health Insurance", "type": "Medical"},
    {"code": "DENTAL", "name": "Dental Insurance", "type": "Dental"},
    {"code": "VISION", "name": "Vision Insurance", "type": "Vision"},
    {"code": "LIFE", "name": "Life Insurance", "type": "Life"},
    {"code": "401K", "name": "401(k) Retirement Plan", "type": "Retirement"},
]

LEARNING_COURSES = [
    {
        "code": "COURSE_LEAD101",
        "name": "Leadership Fundamentals",
        "duration_hours": 8,
        "type": "Instructor-Led",
    },
    {
        "code": "COURSE_TECH201",
        "name": "Advanced Technical Skills",
        "duration_hours": 16,
        "type": "Online",
    },
    {
        "code": "COURSE_COMP301",
        "name": "Compliance Training",
        "duration_hours": 2,
        "type": "Online",
    },
    {
        "code": "COURSE_COMM101",
        "name": "Effective Communication",
        "duration_hours": 4,
        "type": "Instructor-Led",
    },
    {
        "code": "COURSE_PROJ201",
        "name": "Project Management",
        "duration_hours": 12,
        "type": "Blended",
    },
]

SKILLS = [
    {"code": "SKILL_PYTHON", "name": "Python Programming", "category": "Technical"},
    {"code": "SKILL_JAVA", "name": "Java Development", "category": "Technical"},
    {"code": "SKILL_SQL", "name": "SQL Database", "category": "Technical"},
    {"code": "SKILL_LEAD", "name": "Leadership", "category": "Soft Skills"},
    {"code": "SKILL_PRESENT", "name": "Presentation Skills", "category": "Soft Skills"},
    {"code": "SKILL_NEGOTIATION", "name": "Negotiation", "category": "Soft Skills"},
]

ROLES = [
    {"code": "ROLE_ADMIN", "name": "System Administrator"},
    {"code": "ROLE_HR", "name": "HR Administrator"},
    {"code": "ROLE_MGR", "name": "Manager"},
    {"code": "ROLE_EMP", "name": "Employee"},
    {"code": "ROLE_RECRUITER", "name": "Recruiter"},
]

# ── Module-specific reference data ────────────────────────────────────────────

REVIEW_TEMPLATES = [
    {
        "id": "RT00001",
        "name": "Annual Performance Review",
        "review_type": "Annual",
        "frequency": "Annual",
        "rating_scale": "5-point",
    },
    {
        "id": "RT00002",
        "name": "Mid-Year Check-In",
        "review_type": "Mid-Year",
        "frequency": "Semi-Annual",
        "rating_scale": "5-point",
    },
    {
        "id": "RT00003",
        "name": "Probation Review",
        "review_type": "Probation",
        "frequency": "Quarterly",
        "rating_scale": "3-point",
    },
    {
        "id": "RT00004",
        "name": "360 Feedback Review",
        "review_type": "360",
        "frequency": "Annual",
        "rating_scale": "5-point",
    },
]

TALENT_POOLS = [
    {"name": "High Potential", "type": "High Potential"},
    {"name": "Leadership Pipeline", "type": "Leadership Pipeline"},
    {"name": "Technical Expert Pool", "type": "Technical Expert"},
    {"name": "Management Fast Track", "type": "Management"},
    {"name": "Core Talent", "type": "Core Talent"},
    {"name": "Diversity Pipeline", "type": "Diversity"},
]

CAREER_PATHS = [
    {"name": "Individual Contributor to Manager", "typical_years": 3},
    {"name": "Junior to Senior Engineer", "typical_years": 3},
    {"name": "Manager to Director", "typical_years": 4},
    {"name": "Sales Representative to Manager", "typical_years": 3},
    {"name": "Technical Specialist Path", "typical_years": 4},
]

ONBOARDING_PROGRAMS = [
    {"name": "Engineering Onboarding", "duration_days": 30},
    {"name": "Sales Onboarding", "duration_days": 21},
    {"name": "General Employee Onboarding", "duration_days": 14},
    {"name": "Manager Onboarding", "duration_days": 45},
    {"name": "Executive Onboarding", "duration_days": 60},
]
