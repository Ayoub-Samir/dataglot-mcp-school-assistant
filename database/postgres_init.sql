CREATE TABLE departments (
    department_id SMALLINT PRIMARY KEY,
    department_name VARCHAR(100) NOT NULL UNIQUE
);

CREATE TABLE students (
    student_id INTEGER PRIMARY KEY,
    first_name VARCHAR(50) NOT NULL,
    last_name VARCHAR(50) NOT NULL,
    department_id SMALLINT NOT NULL,
    enrollment_year SMALLINT NOT NULL CHECK (enrollment_year BETWEEN 2019 AND 2026),
    status VARCHAR(20) NOT NULL CHECK (status IN ('active', 'graduated', 'on_leave', 'probation')),
    CONSTRAINT fk_students_department
        FOREIGN KEY (department_id) REFERENCES departments (department_id)
);

CREATE INDEX idx_students_department ON students (department_id);
CREATE INDEX idx_students_status ON students (status);
CREATE INDEX idx_students_enrollment_year ON students (enrollment_year);
