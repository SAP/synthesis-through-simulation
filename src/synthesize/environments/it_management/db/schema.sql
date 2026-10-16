-- IT Service Management schema
-- Derived from EnterpriseBench's IT_Service_Management/it_tickets.json
-- and Human_Resource_Management/Employees/employees.json

CREATE TABLE IF NOT EXISTS employee (
    emp_id      TEXT PRIMARY KEY,                       -- EB: "emp_id"
    name        TEXT NOT NULL,                          -- EB: "Name"
    email       TEXT NOT NULL UNIQUE,                   -- EB: "email"
    category    TEXT NOT NULL,                          -- EB: "category" ('IT', 'Engineering', 'HR', 'Finance', 'Business Development')
    level       TEXT,                                   -- EB: "Level"
    salary      INTEGER,                                -- EB: "Salary"
    doj         TEXT NOT NULL,                          -- EB: "DOJ" (date of joining, YYYY-MM-DD)
    is_active   INTEGER NOT NULL DEFAULT 1,             -- EB: "is_valid" ("TRUE"/"FALSE") → 1/0
    reports_to  TEXT REFERENCES employee(emp_id)        -- EB: "reports_to"
);

CREATE TABLE IF NOT EXISTS it_ticket (
    ticket_id           TEXT PRIMARY KEY,               -- EB: "id"
    priority            TEXT NOT NULL,                  -- EB: "priority" ('low'|'medium'|'high')
    status              TEXT NOT NULL DEFAULT 'open',   -- [+] ADDED: explicit state machine
    raised_by_emp_id    TEXT NOT NULL REFERENCES employee(emp_id),  -- EB: "raised_by_emp_id"
    assigned_emp_id     TEXT REFERENCES employee(emp_id),           -- EB: "emp_id" (the resolver)
    assigned_date       TEXT,                           -- EB: "assigned_date" (YYYY-MM-DD)
    created_date        TEXT NOT NULL,                  -- [+] ADDED: for date-order validation
    issue_title         TEXT NOT NULL,                  -- EB: "Issue" (short summary / first line)
    issue_description   TEXT NOT NULL,                  -- EB: "Issue" (full text)
    resolution          TEXT,                           -- EB: "Resolution"
    resolved_date       TEXT                            -- [+] ADDED: for resolved-date validation
);
