-- University Course Registration System schema

CREATE TABLE IF NOT EXISTS student (
    student_id        TEXT PRIMARY KEY,
    name              TEXT NOT NULL,
    email             TEXT NOT NULL UNIQUE,
    academic_program  TEXT NOT NULL,
    enrollment_status TEXT NOT NULL DEFAULT 'active',
    -- 'active', 'inactive', 'graduated', 'suspended'
    gpa               REAL,
    credits_completed INTEGER NOT NULL DEFAULT 0
);

CREATE TABLE IF NOT EXISTS course (
    course_id          TEXT PRIMARY KEY,
    course_code        TEXT NOT NULL UNIQUE,
    title              TEXT NOT NULL,
    instructor         TEXT NOT NULL,
    department         TEXT NOT NULL,
    capacity           INTEGER NOT NULL,
    current_enrollment INTEGER NOT NULL DEFAULT 0,
    credits            INTEGER NOT NULL DEFAULT 3,
    is_open            INTEGER NOT NULL DEFAULT 1
);

CREATE TABLE IF NOT EXISTS enrollment (
    enrollment_id TEXT PRIMARY KEY,
    student_id    TEXT NOT NULL REFERENCES student(student_id),
    course_id     TEXT NOT NULL REFERENCES course(course_id),
    status        TEXT NOT NULL DEFAULT 'enrolled',
    -- 'enrolled', 'dropped', 'completed', 'failed'
    enrolled_date TEXT NOT NULL,
    dropped_date  TEXT,
    UNIQUE(student_id, course_id)
);

CREATE TABLE IF NOT EXISTS waitlist (
    waitlist_id TEXT PRIMARY KEY,
    student_id  TEXT NOT NULL REFERENCES student(student_id),
    course_id   TEXT NOT NULL REFERENCES course(course_id),
    position    INTEGER NOT NULL,
    added_date  TEXT NOT NULL,
    UNIQUE(student_id, course_id)
);

CREATE INDEX IF NOT EXISTS idx_enrollment_student ON enrollment(student_id);
CREATE INDEX IF NOT EXISTS idx_enrollment_course  ON enrollment(course_id);
CREATE INDEX IF NOT EXISTS idx_waitlist_course    ON waitlist(course_id);
