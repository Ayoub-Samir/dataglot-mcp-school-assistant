CREATE TABLE courses (
    course_id INTEGER PRIMARY KEY,
    course_name VARCHAR(120) NOT NULL UNIQUE,
    department_id INTEGER NOT NULL,
    credits TINYINT NOT NULL,
    CONSTRAINT chk_courses_credits CHECK (credits BETWEEN 1 AND 6),
    INDEX idx_courses_department (department_id)
) ENGINE = InnoDB;

CREATE TABLE grades (
    grade_id BIGINT PRIMARY KEY,
    student_id INTEGER NOT NULL,
    course_id INTEGER NOT NULL,
    academic_year VARCHAR(9) NOT NULL,
    semester VARCHAR(10) NOT NULL,
    midterm_score DECIMAL(5,2) NOT NULL,
    final_exam_score DECIMAL(5,2) NOT NULL,
    CONSTRAINT fk_grades_course
        FOREIGN KEY (course_id) REFERENCES courses (course_id),
    CONSTRAINT chk_grades_semester CHECK (semester IN ('Fall', 'Spring')),
    CONSTRAINT chk_grades_midterm CHECK (midterm_score BETWEEN 0 AND 100),
    CONSTRAINT chk_grades_final CHECK (final_exam_score BETWEEN 0 AND 100),
    CONSTRAINT uq_grade_enrollment
        UNIQUE (student_id, course_id, academic_year, semester),
    INDEX idx_grades_student (student_id),
    INDEX idx_grades_course (course_id),
    INDEX idx_grades_year_semester (academic_year, semester)
) ENGINE = InnoDB;

-- student_id and courses.department_id intentionally have no foreign keys to
-- students/departments because those referenced records live in PostgreSQL.
