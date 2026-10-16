-- ===========================
-- HR System - SIMULATED SCHEMA
-- ===========================
-- This expanded schema covers all major HR modules:
-- - Employee Central (EC)
-- - Performance & Goals Management (PM/GM)
-- - Recruiting Management (RCM)
-- - Learning Management (LMS)
-- - Time Management (TM)
-- - Succession Planning (SP)
-- - Compensation Management
-- - Benefits
-- - Onboarding
-- - Career Development Planning
-- ===========================

-- ===========================
-- FOUNDATION OBJECTS (FOD_*)
-- ===========================

-- Companies / Legal Entities
CREATE TABLE fod_company (
    company_code TEXT PRIMARY KEY,
    company_name TEXT NOT NULL,
    country TEXT NOT NULL,
    currency TEXT DEFAULT 'USD',
    status TEXT DEFAULT 'Active',
    created_on TEXT DEFAULT (datetime('now')),
    last_modified_on TEXT DEFAULT (datetime('now'))
);

-- Locations / Work Sites
CREATE TABLE fod_location (
    location_code TEXT PRIMARY KEY,
    location_name TEXT NOT NULL,
    city TEXT,
    state TEXT,
    country TEXT NOT NULL,
    time_zone TEXT,
    address_line1 TEXT,
    postal_code TEXT,
    status TEXT DEFAULT 'Active',
    created_on TEXT DEFAULT (datetime('now')),
    last_modified_on TEXT DEFAULT (datetime('now'))
);

-- Divisions
CREATE TABLE fod_division (
    division_code TEXT PRIMARY KEY,
    division_name TEXT NOT NULL,
    division_head_person_id TEXT,
    status TEXT DEFAULT 'Active',
    created_on TEXT DEFAULT (datetime('now')),
    last_modified_on TEXT DEFAULT (datetime('now'))
);

-- Departments
CREATE TABLE fod_department (
    department_code TEXT PRIMARY KEY,
    department_name TEXT NOT NULL,
    division_code TEXT,
    department_head_person_id TEXT,
    cost_center_code TEXT,
    status TEXT DEFAULT 'Active',
    created_on TEXT DEFAULT (datetime('now')),
    last_modified_on TEXT DEFAULT (datetime('now')),
    FOREIGN KEY (division_code) REFERENCES fod_division(division_code)
);

-- Business Units
CREATE TABLE fod_business_unit (
    bu_code TEXT PRIMARY KEY,
    bu_name TEXT NOT NULL,
    bu_head_person_id TEXT,
    status TEXT DEFAULT 'Active',
    created_on TEXT DEFAULT (datetime('now')),
    last_modified_on TEXT DEFAULT (datetime('now'))
);

-- Cost Centers
CREATE TABLE fod_cost_center (
    cost_center_code TEXT PRIMARY KEY,
    cost_center_name TEXT NOT NULL,
    company_code TEXT,
    status TEXT DEFAULT 'Active',
    created_on TEXT DEFAULT (datetime('now')),
    last_modified_on TEXT DEFAULT (datetime('now'))
);

-- Job Codes / Job Classifications
CREATE TABLE fod_job_code (
    job_code TEXT PRIMARY KEY,
    job_title TEXT NOT NULL,
    job_level TEXT,
    job_family TEXT,
    job_description TEXT,
    flsa_status TEXT, -- Exempt, Non-Exempt
    standard_hours REAL DEFAULT 40.00,
    status TEXT DEFAULT 'Active',
    created_on TEXT DEFAULT (datetime('now')),
    last_modified_on TEXT DEFAULT (datetime('now'))
);

-- Pay Grades / Compensation Bands
CREATE TABLE fod_pay_grade (
    pay_grade_code TEXT PRIMARY KEY,
    pay_grade_name TEXT NOT NULL,
    min_salary DECIMAL(15, 2),
    mid_salary DECIMAL(15, 2),
    max_salary DECIMAL(15, 2),
    currency TEXT DEFAULT 'USD',
    status TEXT DEFAULT 'Active',
    created_on TEXT DEFAULT (datetime('now')),
    last_modified_on TEXT DEFAULT (datetime('now'))
);

-- Positions
CREATE TABLE fod_position (
    position_id TEXT PRIMARY KEY,
    position_title TEXT NOT NULL,
    job_code TEXT,
    department_code TEXT,
    location_code TEXT,
    reports_to_position_id TEXT,
    critical_position INTEGER DEFAULT FALSE,
    position_status TEXT DEFAULT 'Active',
    effective_start_date DATE,
    effective_end_date DATE,
    created_on TEXT DEFAULT (datetime('now')),
    last_modified_on TEXT DEFAULT (datetime('now')),
    FOREIGN KEY (job_code) REFERENCES fod_job_code(job_code),
    FOREIGN KEY (department_code) REFERENCES fod_department(department_code),
    FOREIGN KEY (location_code) REFERENCES fod_location(location_code)
);

-- Pay Components (for compensation)
CREATE TABLE fod_pay_component (
    pay_component_code TEXT PRIMARY KEY,
    pay_component_name TEXT NOT NULL,
    component_type TEXT, -- Base, Bonus, Commission, Allowance, Stock, etc.
    is_recurring INTEGER DEFAULT TRUE,
    is_taxable INTEGER DEFAULT TRUE,
    created_on TEXT DEFAULT (datetime('now'))
);

-- Event Reasons (for status changes)
CREATE TABLE fod_event_reason (
    event_reason_code TEXT PRIMARY KEY,
    event_reason_name TEXT NOT NULL,
    event_type TEXT, -- Hire, Termination, Transfer, Promotion, etc.
    created_on TEXT DEFAULT (datetime('now'))
);

-- Competencies (for performance and succession)
CREATE TABLE fod_competency (
    competency_id TEXT PRIMARY KEY,
    competency_name TEXT NOT NULL,
    competency_description TEXT,
    competency_category TEXT, -- Technical, Leadership, Behavioral
    status TEXT DEFAULT 'Active',
    created_on TEXT DEFAULT (datetime('now'))
);

-- Competency Levels
CREATE TABLE fod_competency_level (
    level_id TEXT PRIMARY KEY,
    competency_id TEXT,
    level_name TEXT, -- Beginner, Intermediate, Advanced, Expert
    level_value INT, -- 1, 2, 3, 4
    level_description TEXT,
    FOREIGN KEY (competency_id) REFERENCES fod_competency(competency_id)
);

-- ===========================
-- PERSON DATA (PER_*)
-- ===========================

-- Core Person Master Data
CREATE TABLE per_person (
    person_id TEXT PRIMARY KEY,
    person_id_external TEXT UNIQUE NOT NULL,
    first_name TEXT NOT NULL,
    last_name TEXT NOT NULL,
    middle_name TEXT,
    preferred_name TEXT,
    date_of_birth DATE,
    gender TEXT,
    nationality TEXT,
    marital_status TEXT,
    person_type TEXT DEFAULT 'Employee', -- Employee, Contingent, Contractor
    created_on TEXT DEFAULT (datetime('now')),
    last_modified_on TEXT DEFAULT (datetime('now'))
);

-- Personal Information (time-dependent)
CREATE TABLE per_personal (
    personal_id INTEGER PRIMARY KEY AUTOINCREMENT,
    person_id TEXT NOT NULL,
    start_date DATE NOT NULL,
    end_date DATE,
    marital_status TEXT,
    address_line1 TEXT,
    address_line2 TEXT,
    city TEXT,
    state TEXT,
    postal_code TEXT,
    country TEXT,
    created_on TEXT DEFAULT (datetime('now')),
    last_modified_on TEXT DEFAULT (datetime('now')),
    FOREIGN KEY (person_id) REFERENCES per_person(person_id) ON DELETE CASCADE
);

-- Email Addresses
CREATE TABLE per_email (
    email_id INTEGER PRIMARY KEY AUTOINCREMENT,
    person_id TEXT NOT NULL,
    email_type TEXT NOT NULL,
    email_address TEXT NOT NULL,
    is_primary INTEGER DEFAULT FALSE,
    created_on TEXT DEFAULT (datetime('now')),
    FOREIGN KEY (person_id) REFERENCES per_person(person_id) ON DELETE CASCADE
);

-- Phone Numbers
CREATE TABLE per_phone (
    phone_id INTEGER PRIMARY KEY AUTOINCREMENT,
    person_id TEXT NOT NULL,
    phone_type TEXT NOT NULL,
    phone_number TEXT NOT NULL,
    is_primary INTEGER DEFAULT FALSE,
    created_on TEXT DEFAULT (datetime('now')),
    FOREIGN KEY (person_id) REFERENCES per_person(person_id) ON DELETE CASCADE
);

-- Emergency Contacts
CREATE TABLE per_emergency_contact (
    contact_id INTEGER PRIMARY KEY AUTOINCREMENT,
    person_id TEXT NOT NULL,
    contact_name TEXT NOT NULL,
    relationship TEXT,
    phone_number TEXT,
    email TEXT,
    is_primary INTEGER DEFAULT FALSE,
    created_on TEXT DEFAULT (datetime('now')),
    FOREIGN KEY (person_id) REFERENCES per_person(person_id) ON DELETE CASCADE
);

-- Dependents
CREATE TABLE per_dependent (
    dependent_id INTEGER PRIMARY KEY AUTOINCREMENT,
    person_id TEXT NOT NULL,
    dependent_name TEXT NOT NULL,
    relationship TEXT, -- Child, Spouse, Domestic Partner
    date_of_birth DATE,
    gender TEXT,
    is_benefit_eligible INTEGER DEFAULT FALSE,
    created_on TEXT DEFAULT (datetime('now')),
    FOREIGN KEY (person_id) REFERENCES per_person(person_id) ON DELETE CASCADE
);

-- Education History
CREATE TABLE per_education (
    education_id INTEGER PRIMARY KEY AUTOINCREMENT,
    person_id TEXT NOT NULL,
    school_name TEXT,
    degree TEXT,
    major TEXT,
    start_date DATE,
    end_date DATE,
    gpa DECIMAL(3, 2),
    created_on TEXT DEFAULT (datetime('now')),
    FOREIGN KEY (person_id) REFERENCES per_person(person_id) ON DELETE CASCADE
);

-- ===========================
-- EMPLOYMENT DATA (EMP_*)
-- ===========================

-- Employment Relationship
CREATE TABLE emp_employment (
    employment_id INTEGER PRIMARY KEY AUTOINCREMENT,
    person_id TEXT NOT NULL,
    user_id TEXT,
    start_date DATE NOT NULL,
    end_date DATE,
    original_start_date DATE,
    seniority_date DATE,
    assignment_class TEXT,
    employee_class TEXT,
    hire_date DATE NOT NULL,
    termination_date DATE,
    termination_reason_code TEXT,
    employment_type TEXT DEFAULT 'Active',
    is_primary INTEGER DEFAULT TRUE,
    created_on TEXT DEFAULT (datetime('now')),
    last_modified_on TEXT DEFAULT (datetime('now')),
    FOREIGN KEY (person_id) REFERENCES per_person(person_id) ON DELETE CASCADE,
    FOREIGN KEY (termination_reason_code) REFERENCES fod_event_reason(event_reason_code)
);

-- Job Information (time-dependent)
CREATE TABLE emp_job (
    job_info_id INTEGER PRIMARY KEY AUTOINCREMENT,
    person_id TEXT NOT NULL,
    user_id TEXT,
    start_date DATE NOT NULL,
    end_date DATE,
    event_reason_code TEXT,
    job_code TEXT NOT NULL,
    position_id TEXT,
    department_code TEXT,
    division_code TEXT,
    location_code TEXT NOT NULL,
    company_code TEXT NOT NULL,
    business_unit_code TEXT,
    cost_center_code TEXT,
    manager_id TEXT,
    pay_grade TEXT,
    fte DECIMAL(3, 2) DEFAULT 1.00,
    standard_hours DECIMAL(5, 2) DEFAULT 40.00,
    employment_status TEXT DEFAULT 'Active',
    probation_end_date DATE,
    is_primary INTEGER DEFAULT TRUE,
    created_on TEXT DEFAULT (datetime('now')),
    last_modified_on TEXT DEFAULT (datetime('now')),
    FOREIGN KEY (person_id) REFERENCES per_person(person_id) ON DELETE CASCADE,
    FOREIGN KEY (event_reason_code) REFERENCES fod_event_reason(event_reason_code),
    FOREIGN KEY (job_code) REFERENCES fod_job_code(job_code),
    FOREIGN KEY (position_id) REFERENCES fod_position(position_id),
    FOREIGN KEY (department_code) REFERENCES fod_department(department_code),
    FOREIGN KEY (division_code) REFERENCES fod_division(division_code),
    FOREIGN KEY (location_code) REFERENCES fod_location(location_code),
    FOREIGN KEY (company_code) REFERENCES fod_company(company_code),
    FOREIGN KEY (business_unit_code) REFERENCES fod_business_unit(bu_code),
    FOREIGN KEY (cost_center_code) REFERENCES fod_cost_center(cost_center_code),
    FOREIGN KEY (pay_grade) REFERENCES fod_pay_grade(pay_grade_code)
);

-- Compensation Information (time-dependent)
CREATE TABLE emp_compensation (
    compensation_id INTEGER PRIMARY KEY AUTOINCREMENT,
    person_id TEXT NOT NULL,
    user_id TEXT,
    start_date DATE NOT NULL,
    end_date DATE,
    pay_component_code TEXT NOT NULL,
    pay_frequency TEXT,
    amount DECIMAL(15, 2) NOT NULL,
    currency TEXT DEFAULT 'USD',
    pay_grade TEXT,
    event_reason_code TEXT,
    created_on TEXT DEFAULT (datetime('now')),
    last_modified_on TEXT DEFAULT (datetime('now')),
    FOREIGN KEY (person_id) REFERENCES per_person(person_id) ON DELETE CASCADE,
    FOREIGN KEY (pay_component_code) REFERENCES fod_pay_component(pay_component_code),
    FOREIGN KEY (pay_grade) REFERENCES fod_pay_grade(pay_grade_code),
    FOREIGN KEY (event_reason_code) REFERENCES fod_event_reason(event_reason_code)
);

-- Stock Grants
CREATE TABLE emp_stock_grant (
    grant_id INTEGER PRIMARY KEY AUTOINCREMENT,
    person_id TEXT NOT NULL,
    grant_date DATE NOT NULL,
    grant_type TEXT, -- RSU, Stock Option, ESPP
    grant_amount DECIMAL(15, 2),
    shares INT,
    vesting_start_date DATE,
    vesting_schedule TEXT, -- 4-year, 3-year monthly, etc.
    status TEXT DEFAULT 'Active',
    created_on TEXT DEFAULT (datetime('now')),
    FOREIGN KEY (person_id) REFERENCES per_person(person_id) ON DELETE CASCADE
);

-- ===========================
-- PERFORMANCE MANAGEMENT (PM_*)
-- ===========================

-- Performance Review Forms/Templates
CREATE TABLE pm_review_template (
    template_id TEXT PRIMARY KEY,
    template_name TEXT NOT NULL,
    review_type TEXT, -- Annual, Mid-Year, Probation, 360
    frequency TEXT, -- Annual, Semi-Annual, Quarterly
    rating_scale TEXT, -- 5-point, 3-point, etc.
    status TEXT DEFAULT 'Active',
    created_on TEXT DEFAULT (datetime('now'))
);

-- Performance Reviews
CREATE TABLE pm_performance_review (
    review_id TEXT PRIMARY KEY,
    person_id TEXT NOT NULL,
    template_id TEXT,
    review_period_start DATE NOT NULL,
    review_period_end DATE NOT NULL,
    review_due_date DATE,
    overall_rating DECIMAL(3, 2),
    overall_rating_label TEXT, -- Exceeds, Meets, Needs Improvement
    reviewer_person_id TEXT, -- Usually manager
    review_status TEXT, -- Draft, In Progress, Completed, Approved
    review_completion_date DATE,
    created_on TEXT DEFAULT (datetime('now')),
    last_modified_on TEXT DEFAULT (datetime('now')),
    FOREIGN KEY (person_id) REFERENCES per_person(person_id) ON DELETE CASCADE,
    FOREIGN KEY (template_id) REFERENCES pm_review_template(template_id),
    FOREIGN KEY (reviewer_person_id) REFERENCES per_person(person_id)
);

-- Performance Review Competencies
CREATE TABLE pm_review_competency (
    review_comp_id INTEGER PRIMARY KEY AUTOINCREMENT,
    review_id TEXT NOT NULL,
    competency_id TEXT NOT NULL,
    rating DECIMAL(3, 2),
    rating_label TEXT,
    comments TEXT,
    created_on TEXT DEFAULT (datetime('now')),
    FOREIGN KEY (review_id) REFERENCES pm_performance_review(review_id) ON DELETE CASCADE,
    FOREIGN KEY (competency_id) REFERENCES fod_competency(competency_id)
);

-- Goals / Objectives
CREATE TABLE pm_goal (
    goal_id TEXT PRIMARY KEY,
    person_id TEXT NOT NULL,
    goal_name TEXT NOT NULL,
    goal_description TEXT,
    goal_type TEXT, -- Individual, Team, Company, Development
    category TEXT, -- Financial, Customer, Process, People
    start_date DATE NOT NULL,
    due_date DATE NOT NULL,
    weight DECIMAL(5, 2), -- Percentage weight (0-100)
    metric TEXT,
    target_value DECIMAL(15, 2),
    actual_value DECIMAL(15, 2),
    status TEXT, -- Not Started, In Progress, On Track, At Risk, Completed
    completion_percentage INT DEFAULT 0,
    final_rating DECIMAL(3, 2),
    created_by_person_id TEXT,
    created_on TEXT DEFAULT (datetime('now')),
    last_modified_on TEXT DEFAULT (datetime('now')),
    FOREIGN KEY (person_id) REFERENCES per_person(person_id) ON DELETE CASCADE
);

-- Goal Comments / Updates
CREATE TABLE pm_goal_comment (
    comment_id INTEGER PRIMARY KEY AUTOINCREMENT,
    goal_id TEXT NOT NULL,
    commenter_person_id TEXT NOT NULL,
    comment_text TEXT NOT NULL,
    comment_date TEXT DEFAULT (datetime('now')),
    FOREIGN KEY (goal_id) REFERENCES pm_goal(goal_id) ON DELETE CASCADE,
    FOREIGN KEY (commenter_person_id) REFERENCES per_person(person_id)
);

-- Continuous Feedback / 360 Feedback
CREATE TABLE pm_feedback (
    feedback_id TEXT PRIMARY KEY,
    subject_person_id TEXT NOT NULL, -- Person receiving feedback
    provider_person_id TEXT NOT NULL, -- Person giving feedback
    feedback_type TEXT, -- Manager, Peer, Direct Report, Self, Customer
    feedback_text TEXT NOT NULL,
    feedback_date DATE NOT NULL,
    is_anonymous INTEGER DEFAULT FALSE,
    sentiment TEXT, -- Positive, Constructive, Neutral
    created_on TEXT DEFAULT (datetime('now')),
    FOREIGN KEY (subject_person_id) REFERENCES per_person(person_id) ON DELETE CASCADE,
    FOREIGN KEY (provider_person_id) REFERENCES per_person(person_id)
);

-- ===========================
-- RECRUITING MANAGEMENT (RCM_*)
-- ===========================

-- Job Requisitions
CREATE TABLE rcm_job_requisition (
    req_id TEXT PRIMARY KEY,
    req_title TEXT NOT NULL,
    job_code TEXT,
    department_code TEXT,
    location_code TEXT,
    hiring_manager_person_id TEXT,
    recruiter_person_id TEXT,
    number_of_openings INT DEFAULT 1,
    employment_type TEXT, -- Full-Time, Part-Time, Contract
    req_status TEXT, -- Draft, Open, On Hold, Filled, Cancelled
    opening_date DATE,
    target_hire_date DATE,
    salary_min DECIMAL(15, 2),
    salary_max DECIMAL(15, 2),
    job_description TEXT,
    requirements TEXT,
    created_on TEXT DEFAULT (datetime('now')),
    last_modified_on TEXT DEFAULT (datetime('now')),
    FOREIGN KEY (job_code) REFERENCES fod_job_code(job_code),
    FOREIGN KEY (department_code) REFERENCES fod_department(department_code),
    FOREIGN KEY (location_code) REFERENCES fod_location(location_code),
    FOREIGN KEY (hiring_manager_person_id) REFERENCES per_person(person_id),
    FOREIGN KEY (recruiter_person_id) REFERENCES per_person(person_id)
);

-- Candidates
CREATE TABLE rcm_candidate (
    candidate_id TEXT PRIMARY KEY,
    first_name TEXT NOT NULL,
    last_name TEXT NOT NULL,
    email TEXT NOT NULL,
    phone TEXT,
    source TEXT, -- LinkedIn, Referral, Career Site, Agency
    current_company TEXT,
    current_title TEXT,
    years_of_experience INT,
    location TEXT,
    resume_file_path TEXT,
    linkedin_url TEXT,
    candidate_status TEXT, -- Active, Hired, Rejected, Withdrawn
    created_on TEXT DEFAULT (datetime('now')),
    last_modified_on TEXT DEFAULT (datetime('now'))
);

-- Job Applications
CREATE TABLE rcm_application (
    application_id TEXT PRIMARY KEY,
    req_id TEXT NOT NULL,
    candidate_id TEXT NOT NULL,
    application_date DATE NOT NULL,
    application_status TEXT, -- New, Under Review, Interview, Offer, Hired, Rejected
    current_stage TEXT, -- Phone Screen, Technical Interview, Final Interview, etc.
    rating DECIMAL(3, 2),
    rejection_reason TEXT,
    offer_extended_date DATE,
    offer_accepted_date DATE,
    expected_start_date DATE,
    created_on TEXT DEFAULT (datetime('now')),
    last_modified_on TEXT DEFAULT (datetime('now')),
    FOREIGN KEY (req_id) REFERENCES rcm_job_requisition(req_id) ON DELETE CASCADE,
    FOREIGN KEY (candidate_id) REFERENCES rcm_candidate(candidate_id) ON DELETE CASCADE
);

-- Interview Schedules
CREATE TABLE rcm_interview (
    interview_id TEXT PRIMARY KEY,
    application_id TEXT NOT NULL,
    interviewer_person_id TEXT NOT NULL,
    interview_type TEXT, -- Phone, Technical, Panel, Hiring Manager
    interview_date TEXT,
    interview_duration_mins INT,
    interview_status TEXT, -- Scheduled, Completed, Cancelled, No Show
    rating DECIMAL(3, 2),
    recommendation TEXT, -- Strong Hire, Hire, Maybe, No Hire
    feedback TEXT,
    created_on TEXT DEFAULT (datetime('now')),
    FOREIGN KEY (application_id) REFERENCES rcm_application(application_id) ON DELETE CASCADE,
    FOREIGN KEY (interviewer_person_id) REFERENCES per_person(person_id)
);

-- Job Offers
CREATE TABLE rcm_offer (
    offer_id TEXT PRIMARY KEY,
    application_id TEXT NOT NULL,
    offer_date DATE NOT NULL,
    offer_expiry_date DATE,
    job_title TEXT,
    start_date DATE,
    base_salary DECIMAL(15, 2),
    currency TEXT DEFAULT 'USD',
    sign_on_bonus DECIMAL(15, 2),
    stock_grant DECIMAL(15, 2),
    offer_status TEXT, -- Draft, Extended, Accepted, Declined, Expired
    accepted_date DATE,
    declined_date DATE,
    decline_reason TEXT,
    created_on TEXT DEFAULT (datetime('now')),
    last_modified_on TEXT DEFAULT (datetime('now')),
    FOREIGN KEY (application_id) REFERENCES rcm_application(application_id) ON DELETE CASCADE
);

-- ===========================
-- ONBOARDING (ONB_*)
-- ===========================

-- Onboarding Programs
CREATE TABLE onb_program (
    program_id TEXT PRIMARY KEY,
    program_name TEXT NOT NULL,
    program_description TEXT,
    duration_days INT,
    status TEXT DEFAULT 'Active',
    created_on TEXT DEFAULT (datetime('now'))
);

-- Onboarding Process Instances
CREATE TABLE onb_onboarding_process (
    process_id TEXT PRIMARY KEY,
    person_id TEXT NOT NULL,
    program_id TEXT,
    start_date DATE NOT NULL,
    target_completion_date DATE,
    actual_completion_date DATE,
    onboarding_status TEXT, -- Not Started, In Progress, Completed
    buddy_person_id TEXT, -- Onboarding buddy
    completion_percentage INT DEFAULT 0,
    created_on TEXT DEFAULT (datetime('now')),
    last_modified_on TEXT DEFAULT (datetime('now')),
    FOREIGN KEY (person_id) REFERENCES per_person(person_id) ON DELETE CASCADE,
    FOREIGN KEY (program_id) REFERENCES onb_program(program_id),
    FOREIGN KEY (buddy_person_id) REFERENCES per_person(person_id)
);

-- Onboarding Tasks
CREATE TABLE onb_task (
    task_id TEXT PRIMARY KEY,
    process_id TEXT NOT NULL,
    task_name TEXT NOT NULL,
    task_description TEXT,
    task_type TEXT, -- Document, Training, Meeting, System Setup
    assigned_to_person_id TEXT,
    due_date DATE,
    completion_date DATE,
    task_status TEXT, -- Not Started, In Progress, Completed, Overdue
    is_mandatory INTEGER DEFAULT TRUE,
    created_on TEXT DEFAULT (datetime('now')),
    FOREIGN KEY (process_id) REFERENCES onb_onboarding_process(process_id) ON DELETE CASCADE,
    FOREIGN KEY (assigned_to_person_id) REFERENCES per_person(person_id)
);

-- ===========================
-- TIME MANAGEMENT (TM_*)
-- ===========================

-- Time Off Types
CREATE TABLE tm_time_off_type (
    time_off_type_code TEXT PRIMARY KEY,
    type_name TEXT NOT NULL,
    is_paid INTEGER DEFAULT TRUE,
    requires_approval INTEGER DEFAULT TRUE,
    max_days_per_year INT,
    can_carryover INTEGER DEFAULT FALSE,
    created_on TEXT DEFAULT (datetime('now'))
);

-- Time Off Balances
CREATE TABLE tm_time_off_balance (
    balance_id INTEGER PRIMARY KEY AUTOINCREMENT,
    person_id TEXT NOT NULL,
    time_off_type_code TEXT NOT NULL,
    year INT NOT NULL,
    accrued_days DECIMAL(6, 2) DEFAULT 0,
    used_days DECIMAL(6, 2) DEFAULT 0,
    pending_days DECIMAL(6, 2) DEFAULT 0,
    available_days DECIMAL(6, 2) DEFAULT 0,
    created_on TEXT DEFAULT (datetime('now')),
    last_modified_on TEXT DEFAULT (datetime('now')),
    FOREIGN KEY (person_id) REFERENCES per_person(person_id) ON DELETE CASCADE,
    FOREIGN KEY (time_off_type_code) REFERENCES tm_time_off_type(time_off_type_code),
    UNIQUE(person_id, time_off_type_code, year)
);

-- Time Off Requests
CREATE TABLE tm_time_off_request (
    request_id TEXT PRIMARY KEY,
    person_id TEXT NOT NULL,
    time_off_type_code TEXT NOT NULL,
    start_date DATE NOT NULL,
    end_date DATE NOT NULL,
    total_days DECIMAL(6, 2) NOT NULL,
    request_status TEXT, -- Pending, Approved, Rejected, Cancelled
    request_date DATE NOT NULL,
    approval_date DATE,
    approver_person_id TEXT,
    rejection_reason TEXT,
    comments TEXT,
    created_on TEXT DEFAULT (datetime('now')),
    last_modified_on TEXT DEFAULT (datetime('now')),
    FOREIGN KEY (person_id) REFERENCES per_person(person_id) ON DELETE CASCADE,
    FOREIGN KEY (time_off_type_code) REFERENCES tm_time_off_type(time_off_type_code),
    FOREIGN KEY (approver_person_id) REFERENCES per_person(person_id)
);

-- Time Sheets
CREATE TABLE tm_timesheet (
    timesheet_id TEXT PRIMARY KEY,
    person_id TEXT NOT NULL,
    week_start_date DATE NOT NULL,
    week_end_date DATE NOT NULL,
    total_hours DECIMAL(6, 2) DEFAULT 0,
    regular_hours DECIMAL(6, 2) DEFAULT 0,
    overtime_hours DECIMAL(6, 2) DEFAULT 0,
    timesheet_status TEXT, -- Draft, Submitted, Approved, Rejected
    submitted_date DATE,
    approved_date DATE,
    approver_person_id TEXT,
    created_on TEXT DEFAULT (datetime('now')),
    last_modified_on TEXT DEFAULT (datetime('now')),
    FOREIGN KEY (person_id) REFERENCES per_person(person_id) ON DELETE CASCADE,
    FOREIGN KEY (approver_person_id) REFERENCES per_person(person_id)
);

-- Timesheet Entries
CREATE TABLE tm_timesheet_entry (
    entry_id INTEGER PRIMARY KEY AUTOINCREMENT,
    timesheet_id TEXT NOT NULL,
    work_date DATE NOT NULL,
    hours DECIMAL(5, 2) NOT NULL,
    project_code TEXT,
    task_code TEXT,
    cost_center_code TEXT,
    comments TEXT,
    created_on TEXT DEFAULT (datetime('now')),
    FOREIGN KEY (timesheet_id) REFERENCES tm_timesheet(timesheet_id) ON DELETE CASCADE,
    FOREIGN KEY (cost_center_code) REFERENCES fod_cost_center(cost_center_code)
);

-- ===========================
-- LEARNING MANAGEMENT (LRN_*)
-- ===========================

-- Learning Courses/Items
CREATE TABLE lrn_course (
    course_id TEXT PRIMARY KEY,
    course_code TEXT UNIQUE NOT NULL,
    course_title TEXT NOT NULL,
    course_description TEXT,
    course_type TEXT, -- Online, Classroom, Webinar, Certification
    provider TEXT,
    duration_hours DECIMAL(5, 2),
    expiration_period_days INT, -- For certifications
    is_mandatory INTEGER DEFAULT FALSE,
    course_status TEXT DEFAULT 'Active',
    created_on TEXT DEFAULT (datetime('now'))
);

-- Learning Assignments
CREATE TABLE lrn_assignment (
    assignment_id TEXT PRIMARY KEY,
    person_id TEXT NOT NULL,
    course_id TEXT NOT NULL,
    assigned_date DATE NOT NULL,
    due_date DATE,
    assignment_type TEXT, -- Mandatory, Recommended, Self-Enrolled
    assigned_by_person_id TEXT,
    created_on TEXT DEFAULT (datetime('now')),
    FOREIGN KEY (person_id) REFERENCES per_person(person_id) ON DELETE CASCADE,
    FOREIGN KEY (course_id) REFERENCES lrn_course(course_id) ON DELETE CASCADE,
    FOREIGN KEY (assigned_by_person_id) REFERENCES per_person(person_id)
);

-- Learning History / Completions
CREATE TABLE lrn_completion (
    completion_id TEXT PRIMARY KEY,
    person_id TEXT NOT NULL,
    course_id TEXT NOT NULL,
    enrollment_date DATE,
    start_date DATE,
    completion_date DATE,
    expiration_date DATE,
    completion_status TEXT, -- Enrolled, In Progress, Completed, Failed, Expired
    score DECIMAL(5, 2),
    pass_fail TEXT, -- Pass, Fail
    certificate_url TEXT,
    created_on TEXT DEFAULT (datetime('now')),
    last_modified_on TEXT DEFAULT (datetime('now')),
    FOREIGN KEY (person_id) REFERENCES per_person(person_id) ON DELETE CASCADE,
    FOREIGN KEY (course_id) REFERENCES lrn_course(course_id) ON DELETE CASCADE
);

-- Certifications
CREATE TABLE lrn_certification (
    certification_id TEXT PRIMARY KEY,
    person_id TEXT NOT NULL,
    certification_name TEXT NOT NULL,
    issuing_organization TEXT,
    issue_date DATE,
    expiration_date DATE,
    certification_number TEXT,
    status TEXT, -- Active, Expired, Renewed
    verification_url TEXT,
    created_on TEXT DEFAULT (datetime('now')),
    FOREIGN KEY (person_id) REFERENCES per_person(person_id) ON DELETE CASCADE
);

-- ===========================
-- SUCCESSION PLANNING (SUC_*)
-- ===========================

-- Succession Plans (for positions)
CREATE TABLE suc_succession_plan (
    plan_id TEXT PRIMARY KEY,
    position_id TEXT NOT NULL,
    incumbent_person_id TEXT, -- Current position holder
    risk_of_loss TEXT, -- High, Medium, Low
    time_to_replacement_months INT,
    plan_status TEXT, -- Active, Inactive
    last_review_date DATE,
    next_review_date DATE,
    created_on TEXT DEFAULT (datetime('now')),
    last_modified_on TEXT DEFAULT (datetime('now')),
    FOREIGN KEY (position_id) REFERENCES fod_position(position_id),
    FOREIGN KEY (incumbent_person_id) REFERENCES per_person(person_id)
);

-- Succession Nominees (potential successors)
CREATE TABLE suc_nominee (
    nominee_id INTEGER PRIMARY KEY AUTOINCREMENT,
    plan_id TEXT NOT NULL,
    nominee_person_id TEXT NOT NULL,
    readiness TEXT, -- Ready Now, 1-2 Years, 3+ Years
    readiness_percentage INT, -- 0-100
    rank INT, -- 1 = top choice
    development_needs TEXT,
    nomination_date DATE,
    status TEXT, -- Active, Promoted, Removed
    created_on TEXT DEFAULT (datetime('now')),
    FOREIGN KEY (plan_id) REFERENCES suc_succession_plan(plan_id) ON DELETE CASCADE,
    FOREIGN KEY (nominee_person_id) REFERENCES per_person(person_id) ON DELETE CASCADE
);

-- High Potential / Talent Pool
CREATE TABLE suc_talent_pool (
    talent_pool_id TEXT PRIMARY KEY,
    pool_name TEXT NOT NULL,
    pool_description TEXT,
    pool_type TEXT, -- High Potential, Leadership Pipeline, Technical Expert
    created_on TEXT DEFAULT (datetime('now'))
);

CREATE TABLE suc_talent_pool_member (
    member_id INTEGER PRIMARY KEY AUTOINCREMENT,
    talent_pool_id TEXT NOT NULL,
    person_id TEXT NOT NULL,
    added_date DATE NOT NULL,
    added_by_person_id TEXT,
    status TEXT, -- Active, Promoted, Removed
    performance_rating TEXT,
    potential_rating TEXT, -- High, Medium, Low
    created_on TEXT DEFAULT (datetime('now')),
    FOREIGN KEY (talent_pool_id) REFERENCES suc_talent_pool(talent_pool_id) ON DELETE CASCADE,
    FOREIGN KEY (person_id) REFERENCES per_person(person_id) ON DELETE CASCADE,
    FOREIGN KEY (added_by_person_id) REFERENCES per_person(person_id)
);

-- ===========================
-- CAREER DEVELOPMENT (CAR_*)
-- ===========================

-- Career Paths
CREATE TABLE car_career_path (
    path_id TEXT PRIMARY KEY,
    path_name TEXT NOT NULL,
    from_job_code TEXT,
    to_job_code TEXT,
    typical_years INT,
    required_competencies TEXT,
    created_on TEXT DEFAULT (datetime('now')),
    FOREIGN KEY (from_job_code) REFERENCES fod_job_code(job_code),
    FOREIGN KEY (to_job_code) REFERENCES fod_job_code(job_code)
);

-- Development Plans
CREATE TABLE car_development_plan (
    plan_id TEXT PRIMARY KEY,
    person_id TEXT NOT NULL,
    plan_name TEXT NOT NULL,
    target_role TEXT,
    target_date DATE,
    plan_status TEXT, -- Active, Completed, Cancelled
    created_date DATE NOT NULL,
    created_on TEXT DEFAULT (datetime('now')),
    last_modified_on TEXT DEFAULT (datetime('now')),
    FOREIGN KEY (person_id) REFERENCES per_person(person_id) ON DELETE CASCADE
);

-- Development Activities
CREATE TABLE car_development_activity (
    activity_id INTEGER PRIMARY KEY AUTOINCREMENT,
    plan_id TEXT NOT NULL,
    activity_name TEXT NOT NULL,
    activity_type TEXT, -- Training, Stretch Assignment, Mentoring, Job Rotation
    activity_description TEXT,
    target_completion_date DATE,
    actual_completion_date DATE,
    activity_status TEXT, -- Not Started, In Progress, Completed
    created_on TEXT DEFAULT (datetime('now')),
    FOREIGN KEY (plan_id) REFERENCES car_development_plan(plan_id) ON DELETE CASCADE
);

-- Mentoring Relationships
CREATE TABLE car_mentoring (
    mentoring_id TEXT PRIMARY KEY,
    mentee_person_id TEXT NOT NULL,
    mentor_person_id TEXT NOT NULL,
    start_date DATE NOT NULL,
    end_date DATE,
    mentoring_status TEXT, -- Active, Completed, Inactive
    focus_areas TEXT,
    created_on TEXT DEFAULT (datetime('now')),
    FOREIGN KEY (mentee_person_id) REFERENCES per_person(person_id) ON DELETE CASCADE,
    FOREIGN KEY (mentor_person_id) REFERENCES per_person(person_id)
);

-- ===========================
-- BENEFITS (BEN_*)
-- ===========================

-- Benefit Plans
CREATE TABLE ben_benefit_plan (
    plan_id TEXT PRIMARY KEY,
    plan_name TEXT NOT NULL,
    plan_type TEXT, -- Medical, Dental, Vision, Life, 401k, FSA, HSA
    plan_category TEXT, -- Health, Insurance, Retirement, Wellness
    provider TEXT,
    plan_year INT,
    employee_cost_monthly DECIMAL(10, 2),
    employer_cost_monthly DECIMAL(10, 2),
    plan_status TEXT DEFAULT 'Active',
    created_on TEXT DEFAULT (datetime('now'))
);

-- Benefit Enrollments
CREATE TABLE ben_enrollment (
    enrollment_id TEXT PRIMARY KEY,
    person_id TEXT NOT NULL,
    plan_id TEXT NOT NULL,
    enrollment_date DATE NOT NULL,
    effective_start_date DATE NOT NULL,
    effective_end_date DATE,
    coverage_level TEXT, -- Employee Only, Employee + Spouse, Family
    enrollment_status TEXT, -- Active, Terminated, Pending
    employee_cost_monthly DECIMAL(10, 2),
    employer_cost_monthly DECIMAL(10, 2),
    created_on TEXT DEFAULT (datetime('now')),
    last_modified_on TEXT DEFAULT (datetime('now')),
    FOREIGN KEY (person_id) REFERENCES per_person(person_id) ON DELETE CASCADE,
    FOREIGN KEY (plan_id) REFERENCES ben_benefit_plan(plan_id)
);

-- Benefit Dependents (linked to enrollments)
CREATE TABLE ben_enrolled_dependent (
    enrolled_dependent_id INTEGER PRIMARY KEY AUTOINCREMENT,
    enrollment_id TEXT NOT NULL,
    dependent_id INT NOT NULL,
    coverage_start_date DATE NOT NULL,
    coverage_end_date DATE,
    created_on TEXT DEFAULT (datetime('now')),
    FOREIGN KEY (enrollment_id) REFERENCES ben_enrollment(enrollment_id) ON DELETE CASCADE,
    FOREIGN KEY (dependent_id) REFERENCES per_dependent(dependent_id) ON DELETE CASCADE
);

-- ===========================
-- COMPENSATION PLANNING (CP_*)
-- ===========================

-- Compensation Review Cycles
CREATE TABLE cp_compensation_cycle (
    cycle_id TEXT PRIMARY KEY,
    cycle_name TEXT NOT NULL,
    cycle_year INT NOT NULL,
    cycle_type TEXT, -- Annual Merit, Bonus, Promotion, Adjustment
    start_date DATE NOT NULL,
    end_date DATE NOT NULL,
    budget_percentage DECIMAL(5, 2),
    cycle_status TEXT, -- Planning, Open, Completed, Closed
    created_on TEXT DEFAULT (datetime('now'))
);

-- Compensation Worksheets
CREATE TABLE cp_worksheet (
    worksheet_id TEXT PRIMARY KEY,
    cycle_id TEXT NOT NULL,
    person_id TEXT NOT NULL,
    current_salary DECIMAL(15, 2),
    proposed_salary DECIMAL(15, 2),
    salary_increase_amount DECIMAL(15, 2),
    salary_increase_percentage DECIMAL(5, 2),
    merit_increase DECIMAL(15, 2),
    promotion_increase DECIMAL(15, 2),
    bonus_amount DECIMAL(15, 2),
    stock_grant_amount DECIMAL(15, 2),
    lump_sum_amount DECIMAL(15, 2),
    compa_ratio DECIMAL(5, 2), -- Comparison to midpoint
    range_penetration DECIMAL(5, 2), -- Position in salary range
    performance_rating TEXT,
    worksheet_status TEXT, -- Draft, Submitted, Approved
    manager_comments TEXT,
    created_on TEXT DEFAULT (datetime('now')),
    last_modified_on TEXT DEFAULT (datetime('now')),
    FOREIGN KEY (cycle_id) REFERENCES cp_compensation_cycle(cycle_id) ON DELETE CASCADE,
    FOREIGN KEY (person_id) REFERENCES per_person(person_id) ON DELETE CASCADE
);

-- ===========================
-- USER ACCOUNTS & SECURITY (USER_*)
-- ===========================

-- User Accounts
CREATE TABLE user_account (
    user_id TEXT PRIMARY KEY,
    username TEXT UNIQUE NOT NULL,
    person_id TEXT,
    email TEXT UNIQUE NOT NULL,
    user_status TEXT DEFAULT 'Active',
    account_locked INTEGER DEFAULT FALSE,
    password_last_changed DATE,
    last_login TEXT,
    failed_login_attempts INT DEFAULT 0,
    created_on TEXT DEFAULT (datetime('now')),
    last_modified_on TEXT DEFAULT (datetime('now')),
    FOREIGN KEY (person_id) REFERENCES per_person(person_id) ON DELETE SET NULL
);

-- User Roles (RBAC)
CREATE TABLE user_role (
    role_id TEXT PRIMARY KEY,
    role_name TEXT NOT NULL,
    role_description TEXT,
    role_type TEXT, -- Admin, Manager, Employee, Recruiter, etc.
    created_on TEXT DEFAULT (datetime('now'))
);

-- User Role Assignments
CREATE TABLE user_role_assignment (
    assignment_id INTEGER PRIMARY KEY AUTOINCREMENT,
    user_id TEXT NOT NULL,
    role_id TEXT NOT NULL,
    assigned_date DATE NOT NULL,
    expiration_date DATE,
    assigned_by_user_id TEXT,
    created_on TEXT DEFAULT (datetime('now')),
    FOREIGN KEY (user_id) REFERENCES user_account(user_id) ON DELETE CASCADE,
    FOREIGN KEY (role_id) REFERENCES user_role(role_id),
    FOREIGN KEY (assigned_by_user_id) REFERENCES user_account(user_id)
);

-- ===========================
-- WORKFLOW & APPROVALS (WF_*)
-- ===========================

-- Workflow Instances
CREATE TABLE wf_workflow_instance (
    workflow_id TEXT PRIMARY KEY,
    workflow_type TEXT NOT NULL, -- TimeOff, Compensation, Hiring, etc.
    subject_person_id TEXT,
    initiator_person_id TEXT NOT NULL,
    workflow_status TEXT, -- Pending, Approved, Rejected, Cancelled
    initiated_date TEXT NOT NULL,
    completed_date TEXT,
    reference_id TEXT, -- ID of the object being approved (request, worksheet, etc.)
    reference_type TEXT, -- Type of object
    created_on TEXT DEFAULT (datetime('now')),
    FOREIGN KEY (subject_person_id) REFERENCES per_person(person_id),
    FOREIGN KEY (initiator_person_id) REFERENCES per_person(person_id)
);

-- Workflow Approval Steps
CREATE TABLE wf_approval_step (
    step_id TEXT PRIMARY KEY,
    workflow_id TEXT NOT NULL,
    step_number INT NOT NULL,
    approver_person_id TEXT NOT NULL,
    step_status TEXT, -- Pending, Approved, Rejected, Skipped
    action_date TEXT,
    comments TEXT,
    created_on TEXT DEFAULT (datetime('now')),
    FOREIGN KEY (workflow_id) REFERENCES wf_workflow_instance(workflow_id) ON DELETE CASCADE,
    FOREIGN KEY (approver_person_id) REFERENCES per_person(person_id)
);

-- ===========================
-- TALENT PROFILE (TP_*)
-- ===========================

-- Skills
CREATE TABLE tp_skill (
    skill_id TEXT PRIMARY KEY,
    skill_name TEXT NOT NULL,
    skill_category TEXT, -- Technical, Soft Skill, Language, Tool
    skill_description TEXT,
    status TEXT DEFAULT 'Active',
    created_on TEXT DEFAULT (datetime('now'))
);

-- Employee Skills
CREATE TABLE tp_employee_skill (
    employee_skill_id INTEGER PRIMARY KEY AUTOINCREMENT,
    person_id TEXT NOT NULL,
    skill_id TEXT NOT NULL,
    proficiency_level TEXT, -- Beginner, Intermediate, Advanced, Expert
    proficiency_rating INT, -- 1-5
    years_of_experience DECIMAL(4, 1),
    last_used_date DATE,
    is_primary_skill INTEGER DEFAULT FALSE,
    validated_by_person_id TEXT,
    validation_date DATE,
    created_on TEXT DEFAULT (datetime('now')),
    last_modified_on TEXT DEFAULT (datetime('now')),
    FOREIGN KEY (person_id) REFERENCES per_person(person_id) ON DELETE CASCADE,
    FOREIGN KEY (skill_id) REFERENCES tp_skill(skill_id),
    FOREIGN KEY (validated_by_person_id) REFERENCES per_person(person_id)
);

-- Languages
CREATE TABLE tp_language (
    language_id INTEGER PRIMARY KEY AUTOINCREMENT,
    person_id TEXT NOT NULL,
    language_code TEXT NOT NULL, -- en, es, fr, de, etc.
    language_name TEXT,
    proficiency_level TEXT, -- Native, Fluent, Intermediate, Basic
    reading_proficiency TEXT,
    writing_proficiency TEXT,
    speaking_proficiency TEXT,
    created_on TEXT DEFAULT (datetime('now')),
    FOREIGN KEY (person_id) REFERENCES per_person(person_id) ON DELETE CASCADE
);

-- Awards & Recognition
CREATE TABLE tp_award (
    award_id TEXT PRIMARY KEY,
    person_id TEXT NOT NULL,
    award_name TEXT NOT NULL,
    award_type TEXT, -- Employee of Month, Innovation Award, etc.
    award_date DATE NOT NULL,
    awarded_by_person_id TEXT,
    award_amount DECIMAL(10, 2),
    award_description TEXT,
    created_on TEXT DEFAULT (datetime('now')),
    FOREIGN KEY (person_id) REFERENCES per_person(person_id) ON DELETE CASCADE,
    FOREIGN KEY (awarded_by_person_id) REFERENCES per_person(person_id)
);

-- ===========================
-- ADDITIONAL PICKLISTS
-- ===========================

-- Countries
CREATE TABLE fod_country (
    country_code TEXT PRIMARY KEY,
    country_name TEXT NOT NULL,
    region TEXT,
    currency_code TEXT
);

-- Currencies
CREATE TABLE fod_currency (
    currency_code TEXT PRIMARY KEY,
    currency_name TEXT NOT NULL,
    currency_symbol TEXT
);

-- ===========================
-- INDEXES FOR PERFORMANCE
-- ===========================

-- Person indexes
CREATE INDEX idx_person_external_id ON per_person(person_id_external);
CREATE INDEX idx_person_last_name ON per_person(last_name);
CREATE INDEX idx_person_type ON per_person(person_type);

-- Employment indexes
CREATE INDEX idx_employment_person ON emp_employment(person_id);
CREATE INDEX idx_employment_dates ON emp_employment(start_date, end_date);
CREATE INDEX idx_employment_type ON emp_employment(employment_type);

-- Job info indexes
CREATE INDEX idx_job_person ON emp_job(person_id);
CREATE INDEX idx_job_manager ON emp_job(manager_id);
CREATE INDEX idx_job_department ON emp_job(department_code);
CREATE INDEX idx_job_location ON emp_job(location_code);
CREATE INDEX idx_job_dates ON emp_job(start_date, end_date);

-- Performance indexes
CREATE INDEX idx_review_person ON pm_performance_review(person_id);
CREATE INDEX idx_review_period ON pm_performance_review(review_period_end);
CREATE INDEX idx_goal_person ON pm_goal(person_id);
CREATE INDEX idx_goal_dates ON pm_goal(start_date, due_date);
CREATE INDEX idx_feedback_subject ON pm_feedback(subject_person_id);

-- Recruiting indexes
CREATE INDEX idx_req_status ON rcm_job_requisition(req_status);
CREATE INDEX idx_req_hiring_mgr ON rcm_job_requisition(hiring_manager_person_id);
CREATE INDEX idx_application_req ON rcm_application(req_id);
CREATE INDEX idx_application_candidate ON rcm_application(candidate_id);
CREATE INDEX idx_application_status ON rcm_application(application_status);

-- Learning indexes
CREATE INDEX idx_assignment_person ON lrn_assignment(person_id);
CREATE INDEX idx_completion_person ON lrn_completion(person_id);
CREATE INDEX idx_completion_course ON lrn_completion(course_id);
CREATE INDEX idx_completion_date ON lrn_completion(completion_date);

-- Time Management indexes
CREATE INDEX idx_timeoff_person ON tm_time_off_request(person_id);
CREATE INDEX idx_timeoff_dates ON tm_time_off_request(start_date, end_date);
CREATE INDEX idx_timeoff_status ON tm_time_off_request(request_status);
CREATE INDEX idx_timesheet_person ON tm_timesheet(person_id);

-- Succession indexes
CREATE INDEX idx_succession_position ON suc_succession_plan(position_id);
CREATE INDEX idx_nominee_plan ON suc_nominee(plan_id);
CREATE INDEX idx_nominee_person ON suc_nominee(nominee_person_id);

-- ===========================
-- END OF SIMULATED SCHEMA
-- ===========================
