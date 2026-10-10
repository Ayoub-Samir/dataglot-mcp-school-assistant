from __future__ import annotations

import pytest

from school_mcp.sql_safety import ReadOnlySQLValidator, SQLSafetyError


@pytest.fixture
def validator() -> ReadOnlySQLValidator:
    return ReadOnlySQLValidator(
        frozenset(
            {
                "pg.public.departments",
                "pg.public.students",
                "mysql.school.courses",
                "mysql.school.grades",
            }
        )
    )


def test_select_and_read_only_cte_are_allowed(validator: ReadOnlySQLValidator) -> None:
    simple = validator.validate("SELECT student_id FROM pg.public.students LIMIT 2")
    cte = validator.validate(
        "WITH scored AS ("
        "SELECT student_id, 0.4 * midterm_score + 0.6 * final_exam_score AS score "
        "FROM mysql.school.grades"
        ") SELECT student_id, AVG(score) FROM scored GROUP BY student_id LIMIT 5"
    )
    assert simple.referenced_tables == ("pg.public.students",)
    assert cte.referenced_tables == ("mysql.school.grades",)


@pytest.mark.parametrize(
    "sql",
    [
        "INSERT INTO pg.public.students (student_id) VALUES (2001)",
        "UPDATE pg.public.students SET status = 'active'",
        "DELETE FROM mysql.school.grades",
        "DROP TABLE pg.public.students",
        "CREATE TABLE pg.public.x (id int)",
        "ALTER TABLE pg.public.students ADD COLUMN x int",
        "TRUNCATE TABLE mysql.school.grades",
        "GRANT SELECT ON pg.public.students TO somebody",
        "REVOKE SELECT ON pg.public.students FROM somebody",
        "COPY pg.public.students TO '/tmp/students.csv'",
        "CALL unsafe_procedure()",
        "SET search_path = public",
        "MERGE INTO pg.public.students s USING pg.public.students x ON false WHEN NOT MATCHED THEN INSERT DEFAULT VALUES",
    ],
)
def test_write_and_control_statements_are_rejected(
    validator: ReadOnlySQLValidator, sql: str
) -> None:
    with pytest.raises(SQLSafetyError):
        validator.validate(sql)


@pytest.mark.parametrize(
    "sql",
    [
        "SELECT 1; SELECT 2",
        "SELECT * FROM pg.public.students -- hide another statement",
        "SELECT * FROM pg.public.students /* comment */",
        "SELECT * FROM students",
        "SELECT * FROM information_schema.tables",
        "SELECT pg_sleep(10)",
        "SELECT pg_read_file('/etc/passwd')",
        "SELECT * FROM pg.public.students FOR UPDATE",
        "WITH changed AS (DELETE FROM mysql.school.grades RETURNING grade_id) SELECT * FROM changed",
    ],
)
def test_bypass_attempts_are_rejected(
    validator: ReadOnlySQLValidator, sql: str
) -> None:
    with pytest.raises(SQLSafetyError):
        validator.validate(sql)


def test_trailing_semicolon_is_allowed(validator: ReadOnlySQLValidator) -> None:
    validated = validator.validate("SELECT COUNT(*) FROM pg.public.students;")
    assert "pg.public.students" in validated.referenced_tables

