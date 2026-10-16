"""
Dataclass models for all HR API return types.
"""

import sqlite3
from dataclasses import dataclass, field
from typing import List, Optional


def row_to_dict(row: sqlite3.Row) -> dict:
    return dict(row) if row else {}


# ── Foundation Objects ────────────────────────────────────────────────────────


@dataclass
class Company:
    company_code: str
    company_name: str
    country: str
    currency: str
    status: str


@dataclass
class Location:
    location_code: str
    location_name: str
    city: Optional[str]
    state: Optional[str]
    country: str
    time_zone: Optional[str]
    status: str


@dataclass
class Department:
    department_code: str
    department_name: str
    division_code: Optional[str]
    department_head_person_id: Optional[str]
    cost_center_code: Optional[str]
    status: str
    headcount: int = 0


@dataclass
class Division:
    division_code: str
    division_name: str
    division_head_person_id: Optional[str]
    status: str


@dataclass
class BusinessUnit:
    bu_code: str
    bu_name: str
    bu_head_person_id: Optional[str]
    status: str


@dataclass
class CostCenter:
    cost_center_code: str
    cost_center_name: str
    company_code: Optional[str]
    status: str


@dataclass
class JobCode:
    job_code: str
    job_title: str
    job_level: Optional[str]
    job_family: Optional[str]
    flsa_status: Optional[str]
    standard_hours: float
    status: str


@dataclass
class PayGrade:
    pay_grade_code: str
    pay_grade_name: str
    min_salary: Optional[float]
    mid_salary: Optional[float]
    max_salary: Optional[float]
    currency: str


@dataclass
class Position:
    position_id: str
    position_title: str
    job_code: Optional[str]
    department_code: Optional[str]
    location_code: Optional[str]
    reports_to_position_id: Optional[str]
    critical_position: bool
    position_status: str


# ── Person / Employee ─────────────────────────────────────────────────────────


@dataclass
class Person:
    person_id: str
    person_id_external: str
    first_name: str
    last_name: str
    middle_name: Optional[str]
    preferred_name: Optional[str]
    date_of_birth: Optional[str]
    gender: Optional[str]
    nationality: Optional[str]
    marital_status: Optional[str]
    person_type: str


@dataclass
class Employment:
    employment_id: int
    person_id: str
    start_date: str
    end_date: Optional[str]
    hire_date: str
    termination_date: Optional[str]
    termination_reason_code: Optional[str]
    employment_type: str
    employee_class: Optional[str]


@dataclass
class JobInfo:
    job_info_id: int
    person_id: str
    start_date: str
    end_date: Optional[str]
    event_reason_code: Optional[str]
    job_code: str
    position_id: Optional[str]
    department_code: Optional[str]
    location_code: str
    company_code: str
    manager_id: Optional[str]
    pay_grade: Optional[str]
    fte: float
    employment_status: str


@dataclass
class Employee:
    """Full employee profile: person + current job + current compensation."""

    person: Person
    employment: Optional[Employment]
    job: Optional[JobInfo]
    emails: List[dict] = field(default_factory=list)
    phones: List[dict] = field(default_factory=list)


# ── Compensation ──────────────────────────────────────────────────────────────


@dataclass
class CompensationRecord:
    compensation_id: int
    person_id: str
    start_date: str
    end_date: Optional[str]
    pay_component_code: str
    pay_frequency: Optional[str]
    amount: float
    currency: str
    pay_grade: Optional[str]
    event_reason_code: Optional[str]


@dataclass
class CompensationCycle:
    cycle_id: str
    cycle_name: str
    cycle_year: int
    cycle_type: str
    start_date: str
    end_date: str
    budget_percentage: Optional[float]
    cycle_status: str


@dataclass
class CompensationWorksheet:
    worksheet_id: str
    cycle_id: str
    person_id: str
    current_salary: Optional[float]
    proposed_salary: Optional[float]
    salary_increase_amount: Optional[float]
    salary_increase_percentage: Optional[float]
    merit_increase: Optional[float]
    bonus_amount: Optional[float]
    stock_grant_amount: Optional[float]
    compa_ratio: Optional[float]
    performance_rating: Optional[str]
    worksheet_status: str
    manager_comments: Optional[str]


# ── Performance ───────────────────────────────────────────────────────────────


@dataclass
class PerformanceReview:
    review_id: str
    person_id: str
    template_id: Optional[str]
    review_period_start: str
    review_period_end: str
    review_due_date: Optional[str]
    overall_rating: Optional[float]
    overall_rating_label: Optional[str]
    reviewer_person_id: Optional[str]
    review_status: str
    review_completion_date: Optional[str]


@dataclass
class Goal:
    goal_id: str
    person_id: str
    goal_name: str
    goal_description: Optional[str]
    goal_type: Optional[str]
    start_date: str
    due_date: str
    weight: Optional[float]
    status: str
    completion_percentage: int
    final_rating: Optional[float]


@dataclass
class Feedback:
    feedback_id: str
    subject_person_id: str
    provider_person_id: str
    feedback_type: Optional[str]
    feedback_text: str
    feedback_date: str
    is_anonymous: bool
    sentiment: Optional[str]


# ── Recruiting ────────────────────────────────────────────────────────────────


@dataclass
class JobRequisition:
    req_id: str
    req_title: str
    job_code: Optional[str]
    department_code: Optional[str]
    location_code: Optional[str]
    hiring_manager_person_id: Optional[str]
    recruiter_person_id: Optional[str]
    number_of_openings: int
    employment_type: Optional[str]
    req_status: str
    opening_date: Optional[str]
    target_hire_date: Optional[str]
    salary_min: Optional[float]
    salary_max: Optional[float]


@dataclass
class Candidate:
    candidate_id: str
    first_name: str
    last_name: str
    email: str
    phone: Optional[str]
    source: Optional[str]
    current_company: Optional[str]
    current_title: Optional[str]
    years_of_experience: Optional[int]
    candidate_status: str


@dataclass
class Application:
    application_id: str
    req_id: str
    candidate_id: str
    application_date: str
    application_status: str
    current_stage: Optional[str]
    rating: Optional[float]
    rejection_reason: Optional[str]
    offer_extended_date: Optional[str]
    offer_accepted_date: Optional[str]


@dataclass
class Interview:
    interview_id: str
    application_id: str
    interviewer_person_id: str
    interview_type: Optional[str]
    interview_date: Optional[str]
    interview_status: str
    rating: Optional[float]
    recommendation: Optional[str]
    feedback: Optional[str]


@dataclass
class Offer:
    offer_id: str
    application_id: str
    offer_date: str
    offer_expiry_date: Optional[str]
    job_title: Optional[str]
    start_date: Optional[str]
    base_salary: Optional[float]
    currency: str
    sign_on_bonus: Optional[float]
    stock_grant: Optional[float]
    offer_status: str


# ── Time Management ───────────────────────────────────────────────────────────


@dataclass
class TimeOffBalance:
    balance_id: int
    person_id: str
    time_off_type_code: str
    year: int
    accrued_days: float
    used_days: float
    pending_days: float
    available_days: float


@dataclass
class TimeOffRequest:
    request_id: str
    person_id: str
    time_off_type_code: str
    start_date: str
    end_date: str
    total_days: float
    request_status: str
    request_date: str
    approval_date: Optional[str]
    approver_person_id: Optional[str]
    rejection_reason: Optional[str]


@dataclass
class Timesheet:
    timesheet_id: str
    person_id: str
    week_start_date: str
    week_end_date: str
    total_hours: float
    regular_hours: float
    overtime_hours: float
    timesheet_status: str
    submitted_date: Optional[str]
    approved_date: Optional[str]


# ── Learning ──────────────────────────────────────────────────────────────────


@dataclass
class Course:
    course_id: str
    course_code: str
    course_title: str
    course_type: Optional[str]
    provider: Optional[str]
    duration_hours: Optional[float]
    is_mandatory: bool
    course_status: str


@dataclass
class LearningAssignment:
    assignment_id: str
    person_id: str
    course_id: str
    assigned_date: str
    due_date: Optional[str]
    assignment_type: Optional[str]


@dataclass
class LearningCompletion:
    completion_id: str
    person_id: str
    course_id: str
    completion_date: Optional[str]
    expiration_date: Optional[str]
    completion_status: str
    score: Optional[float]
    pass_fail: Optional[str]


@dataclass
class Certification:
    certification_id: str
    person_id: str
    certification_name: str
    issuing_organization: Optional[str]
    issue_date: Optional[str]
    expiration_date: Optional[str]
    status: str


# ── Career Development ────────────────────────────────────────────────────────


@dataclass
class CareerPath:
    path_id: str
    path_name: str
    from_job_code: Optional[str]
    to_job_code: Optional[str]
    typical_years: Optional[int]
    required_competencies: Optional[str]


@dataclass
class DevelopmentPlan:
    plan_id: str
    person_id: str
    plan_name: str
    target_role: Optional[str]
    target_date: Optional[str]
    plan_status: str
    created_date: str


@dataclass
class DevelopmentActivity:
    activity_id: int
    plan_id: str
    activity_name: str
    activity_type: Optional[str]
    target_completion_date: Optional[str]
    actual_completion_date: Optional[str]
    activity_status: str


@dataclass
class MentoringRelationship:
    mentoring_id: str
    mentee_person_id: str
    mentor_person_id: str
    start_date: str
    end_date: Optional[str]
    mentoring_status: str
    focus_areas: Optional[str]


# ── Succession ────────────────────────────────────────────────────────────────


@dataclass
class SuccessionPlan:
    plan_id: str
    position_id: str
    incumbent_person_id: Optional[str]
    risk_of_loss: Optional[str]
    time_to_replacement_months: Optional[int]
    plan_status: str
    last_review_date: Optional[str]
    next_review_date: Optional[str]


@dataclass
class Nominee:
    nominee_id: int
    plan_id: str
    nominee_person_id: str
    readiness: Optional[str]
    readiness_percentage: Optional[int]
    rank: Optional[int]
    development_needs: Optional[str]
    status: str


@dataclass
class TalentPool:
    talent_pool_id: str
    pool_name: str
    pool_description: Optional[str]
    pool_type: Optional[str]


@dataclass
class TalentPoolMember:
    member_id: int
    talent_pool_id: str
    person_id: str
    added_date: str
    status: str
    performance_rating: Optional[str]
    potential_rating: Optional[str]


# ── Benefits ──────────────────────────────────────────────────────────────────


@dataclass
class BenefitPlan:
    plan_id: str
    plan_name: str
    plan_type: Optional[str]
    plan_category: Optional[str]
    provider: Optional[str]
    plan_year: Optional[int]
    employee_cost_monthly: Optional[float]
    employer_cost_monthly: Optional[float]
    plan_status: str


@dataclass
class BenefitEnrollment:
    enrollment_id: str
    person_id: str
    plan_id: str
    enrollment_date: str
    effective_start_date: str
    effective_end_date: Optional[str]
    coverage_level: Optional[str]
    enrollment_status: str
    employee_cost_monthly: Optional[float]
    employer_cost_monthly: Optional[float]


@dataclass
class EnrolledDependent:
    enrolled_dependent_id: int
    enrollment_id: str
    dependent_id: int
    coverage_start_date: str
    coverage_end_date: Optional[str]


# ── Talent Profile ────────────────────────────────────────────────────────────


@dataclass
class EmployeeSkill:
    employee_skill_id: int
    person_id: str
    skill_id: str
    proficiency_level: Optional[str]
    proficiency_rating: Optional[int]
    years_of_experience: Optional[float]
    is_primary_skill: bool


@dataclass
class Language:
    language_id: int
    person_id: str
    language_code: str
    language_name: Optional[str]
    proficiency_level: Optional[str]
