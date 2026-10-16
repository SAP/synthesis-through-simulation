"""
Validation script: checks all business rules against the current DB snapshot.

Each check function returns a list of violation dicts.
Run directly:  python validate.py
               python validate.py --db path/to/snapshot.db
               python validate.py --fail-fast   # stop on first violation
               python validate.py --json        # machine-readable output
"""

import argparse
import json
import sqlite3
import sys
from collections import defaultdict
from pathlib import Path

_DEFAULT_DB = Path(__file__).parent / "db" / "hr_barebone.db"
DB_PATH = _DEFAULT_DB  # may be overridden by set_db() or --db flag

# ── helpers ───────────────────────────────────────────────────────────────────


def set_db(path: Path) -> None:
    """Point the validator at a different DB file (for programmatic use)."""
    global DB_PATH
    DB_PATH = Path(path)


def conn():
    c = sqlite3.connect(str(DB_PATH))
    c.row_factory = sqlite3.Row
    return c


def rows(sql, params=()):
    with conn() as c:
        return [dict(r) for r in c.execute(sql, params).fetchall()]


def scalar(sql, params=()):
    with conn() as c:
        r = c.execute(sql, params).fetchone()
        return r[0] if r else None


# ── registry ──────────────────────────────────────────────────────────────────

CHECKS = []


def check(category, rule):
    """Decorator: registers a check function under a category + rule name."""

    def decorator(fn):
        CHECKS.append({"category": category, "rule": rule, "fn": fn})
        return fn

    return decorator


# ════════════════════════════════════════════════════════════════
# EMPLOYEE CENTRAL
# ════════════════════════════════════════════════════════════════


@check("Employee Central", "Active person has exactly one active emp_employment")
def chk_one_active_employment():
    return rows("""
        SELECT p.person_id, p.person_id_external,
               COUNT(e.employment_id) AS active_count
        FROM per_person p
        LEFT JOIN emp_employment e
               ON e.person_id = p.person_id AND e.end_date IS NULL
        WHERE NOT EXISTS (
            SELECT 1 FROM emp_employment te
            WHERE te.person_id = p.person_id
              AND te.employment_type = 'Terminated'
        )
        GROUP BY p.person_id
        HAVING active_count != 1
    """)


@check("Employee Central", "Active employment has exactly one active emp_job")
def chk_one_active_job():
    return rows("""
        SELECT e.employment_id, e.person_id,
               COUNT(j.job_info_id) AS active_count
        FROM emp_employment e
        LEFT JOIN emp_job j
               ON j.person_id = e.person_id AND j.end_date IS NULL
        WHERE e.end_date IS NULL
        GROUP BY e.employment_id
        HAVING active_count != 1
    """)


@check("Employee Central", "Terminated employee has closed emp_job")
def chk_terminated_job_closed():
    return rows("""
        SELECT e.person_id, e.termination_date
        FROM emp_employment e
        JOIN emp_job j ON j.person_id = e.person_id AND j.end_date IS NULL
        WHERE e.termination_date IS NOT NULL
    """)


@check("Employee Central", "manager_id references a valid person_id_external")
def chk_manager_id_valid():
    return rows("""
        SELECT j.job_info_id, j.person_id, j.manager_id
        FROM emp_job j
        WHERE j.manager_id IS NOT NULL
          AND j.end_date IS NULL
          AND j.manager_id NOT IN (
              SELECT person_id_external FROM per_person
          )
    """)


@check("Employee Central", "No circular manager chains (depth-limited BFS)")
def chk_no_circular_managers():
    # Build adjacency: person_id_external -> manager_id
    job_rows = rows("""
        SELECT p.person_id_external, j.manager_id
        FROM emp_job j
        JOIN per_person p ON p.person_id = j.person_id
        WHERE j.end_date IS NULL AND j.manager_id IS NOT NULL
    """)
    mgr_of = {r["person_id_external"]: r["manager_id"] for r in job_rows}
    violations = []
    for start in mgr_of:
        visited = set()
        node = start
        while node in mgr_of:
            if node in visited:
                violations.append({"person_id_external": start, "cycle_at": node})
                break
            visited.add(node)
            node = mgr_of[node]
    return violations


@check("Employee Central", "Terminated employment has a termination_reason_code")
def chk_termination_reason_set():
    return rows("""
        SELECT employment_id, person_id
        FROM emp_employment
        WHERE termination_date IS NOT NULL
          AND (termination_reason_code IS NULL OR termination_reason_code = '')
    """)


# ════════════════════════════════════════════════════════════════
# COMPENSATION
# ════════════════════════════════════════════════════════════════


@check("Compensation", "Active employee has at least one active BASE compensation record")
def chk_has_base_comp():
    return rows("""
        SELECT p.person_id, p.person_id_external
        FROM per_person p
        JOIN emp_employment e ON e.person_id = p.person_id AND e.end_date IS NULL
        WHERE e.termination_date IS NULL
          AND p.person_id NOT IN (
              SELECT c.person_id FROM emp_compensation c
              WHERE c.end_date IS NULL AND c.pay_component_code = 'BASE'
          )
    """)


@check("Compensation", "No duplicate active pay component per employee")
def chk_no_duplicate_active_comp():
    return rows("""
        SELECT person_id, pay_component_code, COUNT(*) AS cnt
        FROM emp_compensation
        WHERE end_date IS NULL
        GROUP BY person_id, pay_component_code
        HAVING cnt > 1
    """)


@check("Compensation", "BASE salary within pay grade band")
def chk_base_salary_in_band():
    return rows("""
        SELECT c.person_id, c.amount, g.min_salary, g.max_salary, g.pay_grade_code
        FROM emp_compensation c
        JOIN emp_job j ON j.person_id = c.person_id AND j.end_date IS NULL
        JOIN fod_pay_grade g ON g.pay_grade_code = j.pay_grade
        WHERE c.pay_component_code = 'BASE'
          AND c.end_date IS NULL
          AND j.pay_grade IS NOT NULL
          AND (c.amount < g.min_salary OR c.amount > g.max_salary * 1.20)
    """)


@check("Compensation", "Compensation event_reason_code references valid fod_event_reason")
def chk_comp_event_reason_valid():
    return rows("""
        SELECT compensation_id, person_id, event_reason_code
        FROM emp_compensation
        WHERE event_reason_code IS NOT NULL
          AND event_reason_code NOT IN (SELECT event_reason_code FROM fod_event_reason)
    """)


@check("Compensation", "Worksheet proposed salary not more than 20% above grade max")
def chk_worksheet_salary_cap():
    return rows("""
        SELECT w.worksheet_id, w.person_id, w.proposed_salary, g.max_salary
        FROM cp_worksheet w
        JOIN emp_job j ON j.person_id = w.person_id AND j.end_date IS NULL
        JOIN fod_pay_grade g ON g.pay_grade_code = j.pay_grade
        WHERE w.proposed_salary IS NOT NULL
          AND j.pay_grade IS NOT NULL
          AND w.proposed_salary > g.max_salary * 1.20
    """)


@check("Compensation", "Compensation cycle: no two Open/Planning cycles same year+type")
def chk_no_duplicate_open_cycles():
    return rows("""
        SELECT cycle_year, cycle_type, COUNT(*) AS cnt
        FROM cp_compensation_cycle
        WHERE cycle_status IN ('Open', 'Planning')
        GROUP BY cycle_year, cycle_type
        HAVING cnt > 1
    """)


# ════════════════════════════════════════════════════════════════
# ORGANIZATION
# ════════════════════════════════════════════════════════════════


@check("Organization", "emp_job.department_code references valid fod_department")
def chk_job_dept_fk():
    return rows("""
        SELECT job_info_id, person_id, department_code
        FROM emp_job
        WHERE department_code IS NOT NULL
          AND department_code NOT IN (SELECT department_code FROM fod_department)
    """)


@check("Organization", "emp_job.location_code references valid fod_location")
def chk_job_location_fk():
    return rows("""
        SELECT job_info_id, person_id, location_code
        FROM emp_job
        WHERE location_code NOT IN (SELECT location_code FROM fod_location)
    """)


@check("Organization", "emp_job.job_code references valid fod_job_code")
def chk_job_code_fk():
    return rows("""
        SELECT job_info_id, person_id, job_code
        FROM emp_job
        WHERE job_code NOT IN (SELECT job_code FROM fod_job_code)
    """)


@check("Organization", "fod_position.reports_to_position_id does not self-reference")
def chk_position_no_self_ref():
    return rows("""
        SELECT position_id, position_title
        FROM fod_position
        WHERE reports_to_position_id = position_id
    """)


@check("Organization", "fod_department.division_code references valid fod_division")
def chk_dept_division_fk():
    return rows("""
        SELECT department_code, department_name, division_code
        FROM fod_department
        WHERE division_code IS NOT NULL
          AND division_code NOT IN (SELECT division_code FROM fod_division)
    """)


# ════════════════════════════════════════════════════════════════
# PERFORMANCE & GOALS
# ════════════════════════════════════════════════════════════════


@check("Performance", "Completed review has overall_rating set")
def chk_completed_review_has_rating():
    return rows("""
        SELECT review_id, person_id, review_status
        FROM pm_performance_review
        WHERE review_status = 'Completed'
          AND (overall_rating IS NULL OR overall_rating = 0)
    """)


@check("Performance", "No overlapping review periods for same person")
def chk_no_overlapping_reviews():
    return rows("""
        SELECT a.review_id AS review_a, b.review_id AS review_b, a.person_id
        FROM pm_performance_review a
        JOIN pm_performance_review b
          ON a.person_id = b.person_id
         AND a.review_id < b.review_id
         AND a.review_status NOT IN ('Cancelled')
         AND b.review_status NOT IN ('Cancelled')
         AND a.review_period_start <= b.review_period_end
         AND a.review_period_end   >= b.review_period_start
    """)


@check("Performance", "Goal weights per employee do not exceed 100")
def chk_goal_weight_cap():
    return rows("""
        SELECT person_id, ROUND(SUM(weight), 2) AS total_weight
        FROM pm_goal
        WHERE status NOT IN ('Completed', 'Cancelled')
          AND weight IS NOT NULL
        GROUP BY person_id
        HAVING total_weight > 100
    """)


@check("Performance", "Completed goals have completion_percentage = 100")
def chk_completed_goal_100pct():
    return rows("""
        SELECT goal_id, person_id, status, completion_percentage
        FROM pm_goal
        WHERE status = 'Completed'
          AND (completion_percentage IS NULL OR completion_percentage < 100)
    """)


@check("Performance", "Goal due_date >= start_date")
def chk_goal_dates():
    return rows("""
        SELECT goal_id, person_id, start_date, due_date
        FROM pm_goal
        WHERE due_date < start_date
    """)


@check("Performance", "pm_review_competency references valid fod_competency")
def chk_review_comp_fk():
    return rows("""
        SELECT review_comp_id, review_id, competency_id
        FROM pm_review_competency
        WHERE competency_id NOT IN (SELECT competency_id FROM fod_competency)
    """)


@check("Performance", "Feedback: subject and provider are different people")
def chk_feedback_no_self():
    return rows("""
        SELECT feedback_id, subject_person_id, provider_person_id
        FROM pm_feedback
        WHERE subject_person_id = provider_person_id
    """)


# ════════════════════════════════════════════════════════════════
# RECRUITING
# ════════════════════════════════════════════════════════════════


@check("Recruiting", "No candidate has two active applications to the same req")
def chk_no_duplicate_applications():
    return rows("""
        SELECT req_id, candidate_id, COUNT(*) AS cnt
        FROM rcm_application
        WHERE application_status NOT IN ('Rejected', 'Withdrawn')
        GROUP BY req_id, candidate_id
        HAVING cnt > 1
    """)


@check("Recruiting", "Accepted offers have accepted_date set")
def chk_offer_accepted_date():
    return rows("""
        SELECT offer_id, application_id, offer_status
        FROM rcm_offer
        WHERE offer_status = 'Accepted'
          AND (accepted_date IS NULL OR accepted_date = '')
    """)


@check("Recruiting", "Declined offers have declined_date set")
def chk_offer_declined_date():
    return rows("""
        SELECT offer_id, application_id, offer_status
        FROM rcm_offer
        WHERE offer_status = 'Declined'
          AND (declined_date IS NULL OR declined_date = '')
    """)


@check("Recruiting", "Hired application count does not exceed req number_of_openings")
def chk_req_headcount():
    return rows("""
        SELECT a.req_id, r.number_of_openings,
               COUNT(*) AS hired_count
        FROM rcm_application a
        JOIN rcm_job_requisition r ON r.req_id = a.req_id
        WHERE a.application_status = 'Hired'
        GROUP BY a.req_id, r.number_of_openings
        HAVING hired_count > r.number_of_openings
    """)


@check("Recruiting", "Open req has a valid hiring_manager_person_id")
def chk_req_hiring_mgr_valid():
    return rows("""
        SELECT req_id, req_title, hiring_manager_person_id
        FROM rcm_job_requisition
        WHERE req_status = 'Open'
          AND hiring_manager_person_id IS NOT NULL
          AND hiring_manager_person_id NOT IN (SELECT person_id FROM per_person)
    """)


@check("Recruiting", "Interview has a valid interviewer_person_id")
def chk_interview_person_fk():
    return rows("""
        SELECT interview_id, application_id, interviewer_person_id
        FROM rcm_interview
        WHERE interviewer_person_id NOT IN (SELECT person_id FROM per_person)
    """)


# ════════════════════════════════════════════════════════════════
# TIME MANAGEMENT
# ════════════════════════════════════════════════════════════════


@check("Time Management", "No overlapping Approved/Pending requests per employee per type")
def chk_no_overlapping_timeoff():
    return rows("""
        SELECT a.request_id AS req_a, b.request_id AS req_b,
               a.person_id, a.time_off_type_code
        FROM tm_time_off_request a
        JOIN tm_time_off_request b
          ON a.person_id           = b.person_id
         AND a.time_off_type_code  = b.time_off_type_code
         AND a.request_id          < b.request_id
         AND a.request_status      IN ('Approved', 'Pending')
         AND b.request_status      IN ('Approved', 'Pending')
         AND a.start_date          <= b.end_date
         AND a.end_date            >= b.start_date
    """)


@check("Time Management", "Approved time-off request has approver_person_id set")
def chk_approved_has_approver():
    return rows("""
        SELECT request_id, person_id
        FROM tm_time_off_request
        WHERE request_status = 'Approved'
          AND (approver_person_id IS NULL OR approver_person_id = '')
    """)


@check("Time Management", "Time-off balance: available_days >= 0")
def chk_balance_non_negative():
    return rows("""
        SELECT balance_id, person_id, time_off_type_code, year, available_days
        FROM tm_time_off_balance
        WHERE available_days < 0
    """)


@check("Time Management", "Timesheet total_hours matches sum of entries")
def chk_timesheet_hours_match():
    return rows("""
        SELECT t.timesheet_id, t.person_id,
               t.total_hours AS stored_total,
               ROUND(COALESCE(SUM(e.hours), 0), 2) AS computed_total
        FROM tm_timesheet t
        LEFT JOIN tm_timesheet_entry e ON e.timesheet_id = t.timesheet_id
        GROUP BY t.timesheet_id
        HAVING ABS(stored_total - computed_total) > 0.01
    """)


@check("Time Management", "Timesheet week_end_date = week_start_date + 6 days")
def chk_timesheet_week_range():
    return rows("""
        SELECT timesheet_id, person_id, week_start_date, week_end_date
        FROM tm_timesheet
        WHERE julianday(week_end_date) - julianday(week_start_date) != 6
    """)


@check("Time Management", "No duplicate timesheets per employee per week")
def chk_no_duplicate_timesheets():
    return rows("""
        SELECT person_id, week_start_date, COUNT(*) AS cnt
        FROM tm_timesheet
        GROUP BY person_id, week_start_date
        HAVING cnt > 1
    """)


@check("Time Management", "Timesheet entry work_date within week range")
def chk_entry_within_week():
    return rows("""
        SELECT e.entry_id, e.timesheet_id, e.work_date,
               t.week_start_date, t.week_end_date
        FROM tm_timesheet_entry e
        JOIN tm_timesheet t ON t.timesheet_id = e.timesheet_id
        WHERE e.work_date < t.week_start_date
           OR e.work_date > t.week_end_date
    """)


@check("Time Management", "No single work_date exceeds 24 hours in a timesheet")
def chk_daily_hours_cap():
    return rows("""
        SELECT e.timesheet_id, e.work_date, SUM(e.hours) AS total_hours
        FROM tm_timesheet_entry e
        GROUP BY e.timesheet_id, e.work_date
        HAVING total_hours > 24
    """)


# ════════════════════════════════════════════════════════════════
# LEARNING
# ════════════════════════════════════════════════════════════════


@check("Learning", "Expired certifications have status='Expired'")
def chk_cert_expiry_status():
    return rows("""
        SELECT certification_id, person_id, certification_name,
               expiration_date, status
        FROM lrn_certification
        WHERE expiration_date < date('now')
          AND status NOT IN ('Expired', 'Revoked')
    """)


@check("Learning", "Completed person+course has no open assignment")
def chk_completed_no_open_assignment():
    return rows("""
        SELECT a.assignment_id, a.person_id, a.course_id
        FROM lrn_assignment a
        JOIN lrn_completion c
          ON c.person_id = a.person_id AND c.course_id = a.course_id
        WHERE c.completion_status = 'Completed'
    """)


@check("Learning", "No duplicate assignments for same person+course")
def chk_no_duplicate_assignments():
    return rows("""
        SELECT person_id, course_id, COUNT(*) AS cnt
        FROM lrn_assignment
        GROUP BY person_id, course_id
        HAVING cnt > 1
    """)


@check("Learning", "lrn_assignment.course_id references an Active course")
def chk_assignment_active_course():
    return rows("""
        SELECT a.assignment_id, a.person_id, a.course_id
        FROM lrn_assignment a
        JOIN lrn_course c ON c.course_id = a.course_id
        WHERE c.course_status != 'Active'
    """)


@check("Learning", "Completion score >= 70 should be Pass; < 70 should be Fail")
def chk_pass_fail_consistency():
    return rows("""
        SELECT completion_id, person_id, course_id, score, pass_fail
        FROM lrn_completion
        WHERE score IS NOT NULL AND pass_fail IS NOT NULL
          AND (
              (score >= 70 AND pass_fail = 'Fail')
           OR (score <  70 AND pass_fail = 'Pass')
          )
    """)


# ════════════════════════════════════════════════════════════════
# CAREER DEVELOPMENT
# ════════════════════════════════════════════════════════════════


@check("Career", "Completed development plan has all activities completed")
def chk_plan_completion_gate():
    return rows("""
        SELECT dp.plan_id, dp.person_id, dp.plan_status,
               COUNT(a.activity_id) AS incomplete_activities
        FROM car_development_plan dp
        JOIN car_development_activity a ON a.plan_id = dp.plan_id
        WHERE dp.plan_status = 'Completed'
          AND a.activity_status != 'Completed'
        GROUP BY dp.plan_id
    """)


@check("Career", "No mentee has more than 2 active mentoring relationships")
def chk_mentoring_cap():
    return rows("""
        SELECT mentee_person_id, COUNT(*) AS active_count
        FROM car_mentoring
        WHERE mentoring_status = 'Active'
        GROUP BY mentee_person_id
        HAVING active_count > 2
    """)


@check("Career", "No self-mentoring relationships")
def chk_no_self_mentoring():
    return rows("""
        SELECT mentoring_id, mentee_person_id, mentor_person_id
        FROM car_mentoring
        WHERE mentee_person_id = mentor_person_id
    """)


@check("Career", "No duplicate active mentoring pair")
def chk_no_duplicate_mentoring():
    return rows("""
        SELECT mentee_person_id, mentor_person_id, COUNT(*) AS cnt
        FROM car_mentoring
        WHERE mentoring_status = 'Active'
        GROUP BY mentee_person_id, mentor_person_id
        HAVING cnt > 1
    """)


@check("Career", "No duplicate skill per employee")
def chk_no_duplicate_skills():
    return rows("""
        SELECT person_id, skill_id, COUNT(*) AS cnt
        FROM tp_employee_skill
        GROUP BY person_id, skill_id
        HAVING cnt > 1
    """)


@check("Career", "Activity target_completion_date within plan target_date")
def chk_activity_within_plan_date():
    return rows("""
        SELECT a.activity_id, a.plan_id,
               a.target_completion_date, dp.target_date
        FROM car_development_activity a
        JOIN car_development_plan dp ON dp.plan_id = a.plan_id
        WHERE dp.target_date IS NOT NULL
          AND a.target_completion_date IS NOT NULL
          AND a.target_completion_date > dp.target_date
    """)


@check("Career", "No duplicate career path (same from/to job_code)")
def chk_no_duplicate_career_path():
    return rows("""
        SELECT from_job_code, to_job_code, COUNT(*) AS cnt
        FROM car_career_path
        WHERE from_job_code IS NOT NULL AND to_job_code IS NOT NULL
        GROUP BY from_job_code, to_job_code
        HAVING cnt > 1
    """)


@check("Career", "Career path from_job_code != to_job_code")
def chk_career_path_no_self_loop():
    return rows("""
        SELECT path_id, path_name, from_job_code, to_job_code
        FROM car_career_path
        WHERE from_job_code = to_job_code
    """)


# ════════════════════════════════════════════════════════════════
# SUCCESSION
# ════════════════════════════════════════════════════════════════


@check("Succession", "No more than one Active plan per position")
def chk_one_active_plan_per_position():
    return rows("""
        SELECT position_id, COUNT(*) AS cnt
        FROM suc_succession_plan
        WHERE plan_status = 'Active'
        GROUP BY position_id
        HAVING cnt > 1
    """)


@check("Succession", "Nominee is not the incumbent of the same plan")
def chk_nominee_not_incumbent():
    return rows("""
        SELECT n.nominee_id, n.plan_id,
               n.nominee_person_id, sp.incumbent_person_id
        FROM suc_nominee n
        JOIN suc_succession_plan sp ON sp.plan_id = n.plan_id
        WHERE n.nominee_person_id = sp.incumbent_person_id
          AND n.status = 'Active'
    """)


@check("Succession", "No duplicate Active nominee per plan")
def chk_no_duplicate_nominee():
    return rows("""
        SELECT plan_id, nominee_person_id, COUNT(*) AS cnt
        FROM suc_nominee
        WHERE status = 'Active'
        GROUP BY plan_id, nominee_person_id
        HAVING cnt > 1
    """)


@check("Succession", "Talent pool type is one of the allowed values")
def chk_talent_pool_type():
    with conn() as c:
        return [
            dict(r)
            for r in c.execute("""
            SELECT talent_pool_id, pool_name, pool_type
            FROM suc_talent_pool
            WHERE pool_type NOT IN
                  ('High Potential','Leadership','Technical','Management',
                   'Core Talent','Diversity','Leadership Pipeline','Technical Expert')
        """).fetchall()
        ]


@check("Succession", "No duplicate Active pool member per talent pool")
def chk_no_duplicate_pool_member():
    return rows("""
        SELECT talent_pool_id, person_id, COUNT(*) AS cnt
        FROM suc_talent_pool_member
        WHERE status = 'Active'
        GROUP BY talent_pool_id, person_id
        HAVING cnt > 1
    """)


# ════════════════════════════════════════════════════════════════
# BENEFITS
# ════════════════════════════════════════════════════════════════


@check("Benefits", "No duplicate Active enrollment per person per plan")
def chk_no_duplicate_enrollment():
    return rows("""
        SELECT person_id, plan_id, COUNT(*) AS cnt
        FROM ben_enrollment
        WHERE enrollment_status = 'Active'
        GROUP BY person_id, plan_id
        HAVING cnt > 1
    """)


@check("Benefits", "Non 'Employee Only' enrollment has at least one enrolled dependent")
def chk_enrollment_has_dependents():
    return rows("""
        SELECT e.enrollment_id, e.person_id, e.coverage_level
        FROM ben_enrollment e
        LEFT JOIN ben_enrolled_dependent d
               ON d.enrollment_id = e.enrollment_id
              AND (d.coverage_end_date IS NULL OR d.coverage_end_date >= date('now'))
        WHERE e.enrollment_status = 'Active'
          AND e.coverage_level != 'Employee Only'
        GROUP BY e.enrollment_id
        HAVING COUNT(d.enrolled_dependent_id) = 0
    """)


@check("Benefits", "Terminated enrollment has effective_end_date set")
def chk_terminated_enrollment_date():
    return rows("""
        SELECT enrollment_id, person_id, enrollment_status
        FROM ben_enrollment
        WHERE enrollment_status = 'Terminated'
          AND (effective_end_date IS NULL OR effective_end_date = '')
    """)


@check("Benefits", "Enrolled dependent belongs to the enrolling employee")
def chk_dependent_ownership():
    return rows("""
        SELECT ed.enrolled_dependent_id, ed.enrollment_id,
               ed.dependent_id, e.person_id AS enrolled_person,
               d.person_id AS dependent_owner
        FROM ben_enrolled_dependent ed
        JOIN ben_enrollment e   ON e.enrollment_id   = ed.enrollment_id
        JOIN per_dependent  d   ON d.dependent_id    = ed.dependent_id
        WHERE e.person_id != d.person_id
    """)


@check("Benefits", "benefit_plan type is one of the allowed values")
def chk_benefit_plan_type():
    with conn() as c:
        return [
            dict(r)
            for r in c.execute("""
            SELECT plan_id, plan_name, plan_type
            FROM ben_benefit_plan
            WHERE plan_type NOT IN
                  ('Medical','Dental','Vision','Life','401k','FSA','HSA','Retirement')
        """).fetchall()
        ]


# ════════════════════════════════════════════════════════════════
# RUNNER
# ════════════════════════════════════════════════════════════════

PASS = "\033[32m✓\033[0m"
FAIL = "\033[31m✗\033[0m"
WARN = "\033[33m!\033[0m"
RESET = "\033[0m"


def run(fail_fast=False, as_json=False, show_sample=3):
    results = []
    category_totals = defaultdict(lambda: {"checks": 0, "violations": 0})

    for entry in CHECKS:
        cat, rule, fn = entry["category"], entry["rule"], entry["fn"]
        try:
            violations = fn()
        except Exception as exc:
            violations = [{"error": str(exc)}]

        count = len(violations)
        category_totals[cat]["checks"] += 1
        category_totals[cat]["violations"] += 1 if count else 0

        result = {
            "category": cat,
            "rule": rule,
            "status": "PASS" if count == 0 else "FAIL",
            "violation_count": count,
            "sample": violations[:show_sample],
        }
        results.append(result)

        if not as_json:
            icon = PASS if count == 0 else FAIL
            print(f"  {icon}  [{cat}] {rule}")
            if count:
                print(f"       {WARN}  {count} violation(s)")
                for v in violations[:show_sample]:
                    print(f"         {v}")

        if fail_fast and count:
            break

    if as_json:
        print(json.dumps(results, indent=2))
        return results

    # Summary
    total_checks = len(results)
    total_fails = sum(1 for r in results if r["status"] == "FAIL")
    total_pass = total_checks - total_fails

    print()
    print("─" * 60)
    print(f"  Checks:  {total_checks}")
    print(f"  {'Passed:':9}{PASS} {total_pass}")
    print(
        f"  {'Failed:':9}{FAIL} {total_fails}" if total_fails else f"  {'Failed:':9}  {total_fails}"
    )
    print()
    print("  By category:")
    for cat, totals in sorted(category_totals.items()):
        status = PASS if totals["violations"] == 0 else FAIL
        print(f"    {status}  {cat:30s}  {totals['checks']} checks, {totals['violations']} failing")
    print("─" * 60)

    return results


if __name__ == "__main__":
    parser = argparse.ArgumentParser(description="HR DB business-rule validator")
    parser.add_argument(
        "--db", type=Path, default=None, help="Path to DB file (default: hr_barebone.db)"
    )
    parser.add_argument(
        "--fail-fast", action="store_true", help="Stop after the first failing check"
    )
    parser.add_argument("--json", action="store_true", help="Output results as JSON")
    parser.add_argument(
        "--sample", type=int, default=3, help="Max violation rows to show per check (default: 3)"
    )
    args = parser.parse_args()

    if args.db:
        set_db(args.db)

    results = run(fail_fast=args.fail_fast, as_json=args.json, show_sample=args.sample)
    sys.exit(1 if any(r["status"] == "FAIL" for r in results) else 0)
