#!/usr/bin/env python3
"""Generate deterministic SQL seed files for the school federation project."""

from __future__ import annotations

import argparse
import random
from pathlib import Path
from typing import Sequence


SEED = 20260924
STUDENT_COUNT = 1_000
GRADES_PER_STUDENT = 6

DEPARTMENTS = [
    (1, "Computer Science"),
    (2, "Business Administration"),
    (3, "Mechanical Engineering"),
    (4, "Psychology"),
    (5, "Mathematics"),
]

# id, name, department_id, credits, relative difficulty
COURSES = [
    (1, "Introduction to Programming", 1, 4, 1),
    (2, "Data Structures", 1, 4, 3),
    (3, "Database Systems", 1, 3, 1),
    (4, "Computer Networks", 1, 3, 2),
    (5, "Software Engineering", 1, 4, 0),
    (6, "Operating Systems", 1, 4, 4),
    (7, "Web Application Development", 1, 3, -1),
    (8, "Artificial Intelligence", 1, 4, 3),
    (9, "Principles of Management", 2, 3, -1),
    (10, "Financial Accounting", 2, 3, 2),
    (11, "Marketing Fundamentals", 2, 3, -2),
    (12, "Business Statistics", 2, 3, 2),
    (13, "Organizational Behavior", 2, 3, -1),
    (14, "Corporate Finance", 2, 4, 3),
    (15, "Operations Management", 2, 3, 1),
    (16, "Business Strategy", 2, 3, 0),
    (17, "Engineering Mechanics", 3, 4, 3),
    (18, "Thermodynamics", 3, 4, 5),
    (19, "Fluid Mechanics", 3, 4, 4),
    (20, "Materials Science", 3, 3, 2),
    (21, "Machine Design", 3, 4, 4),
    (22, "Manufacturing Processes", 3, 3, 1),
    (23, "Heat Transfer", 3, 4, 5),
    (24, "Control Systems", 3, 4, 3),
    (25, "Introduction to Psychology", 4, 3, -2),
    (26, "Developmental Psychology", 4, 3, 0),
    (27, "Social Psychology", 4, 3, -1),
    (28, "Cognitive Psychology", 4, 4, 2),
    (29, "Research Methods in Psychology", 4, 3, 2),
    (30, "Personality Psychology", 4, 3, 0),
    (31, "Abnormal Psychology", 4, 3, 1),
    (32, "Educational Psychology", 4, 3, -1),
    (33, "Calculus I", 5, 4, 3),
    (34, "Calculus II", 5, 4, 5),
    (35, "Linear Algebra", 5, 4, 4),
    (36, "Discrete Mathematics", 5, 3, 2),
    (37, "Probability Theory", 5, 4, 4),
    (38, "Numerical Analysis", 5, 3, 3),
    (39, "Abstract Algebra", 5, 4, 6),
    (40, "Mathematical Modeling", 5, 3, 2),
]

FIRST_NAMES = [
    "Ahmet", "Aisha", "Ali", "Amelia", "Ayse", "Can", "Daniel", "Defne",
    "Elena", "Elif", "Emir", "Emma", "Eren", "Fatima", "Gabriel", "Hana",
    "Isabella", "Jack", "Kerem", "Lara", "Leyla", "Liam", "Maya", "Mehmet",
    "Mert", "Mia", "Nora", "Omar", "Selin", "Sofia", "Thomas", "Yasemin",
]

LAST_NAMES = [
    "Aksoy", "Arslan", "Aydin", "Brown", "Celik", "Demir", "Dogan", "Garcia",
    "Gunes", "Johnson", "Kaya", "Kilic", "Koc", "Martin", "Martinez", "Miller",
    "Ozdemir", "Patel", "Rodriguez", "Sahin", "Smith", "Taylor", "Thompson",
    "Walker", "Williams", "Yildiz", "Yilmaz", "Young",
]

DEPARTMENT_EFFECT = {1: 3.0, 2: 0.5, 3: -2.0, 4: 2.0, 5: -3.5}


def sql_string(value: str) -> str:
    return "'" + value.replace("'", "''") + "'"


def insert_statements(
    table: str,
    columns: Sequence[str],
    rows: Sequence[Sequence[object]],
    chunk_size: int = 500,
) -> str:
    statements: list[str] = []
    for start in range(0, len(rows), chunk_size):
        values = []
        for row in rows[start : start + chunk_size]:
            rendered = [sql_string(v) if isinstance(v, str) else str(v) for v in row]
            values.append("(" + ", ".join(rendered) + ")")
        statements.append(
            f"INSERT INTO {table} ({', '.join(columns)}) VALUES\n  "
            + ",\n  ".join(values)
            + ";"
        )
    return "\n\n".join(statements)


def clipped_score(value: float) -> float:
    return round(max(0.0, min(100.0, value)), 2)


def choose_status(rng: random.Random, enrollment_year: int, ability: float) -> str:
    draw = rng.random()
    if ability < 50 and draw < 0.45:
        return "probation"
    if enrollment_year <= 2021 and draw < 0.42:
        return "graduated"
    if draw < 0.05:
        return "on_leave"
    return "active"


def build_rows() -> tuple[
    list[tuple[object, ...]],
    list[tuple[object, ...]],
    list[tuple[object, ...]],
]:
    rng = random.Random(SEED)
    students: list[tuple[object, ...]] = []
    student_profiles: list[tuple[int, int, float]] = []

    for student_id in range(1, STUDENT_COUNT + 1):
        department_id = ((student_id - 1) % len(DEPARTMENTS)) + 1
        enrollment_year = rng.choices(
            [2021, 2022, 2023, 2024, 2025],
            weights=[12, 18, 22, 24, 24],
            k=1,
        )[0]
        ability = rng.gauss(72.0, 11.5)
        profile_draw = rng.random()
        if profile_draw < 0.07:
            ability = rng.uniform(36.0, 50.0)
        elif profile_draw > 0.93:
            ability = rng.uniform(90.0, 97.0)
        ability = max(30.0, min(98.0, ability))
        status = choose_status(rng, enrollment_year, ability)
        students.append(
            (
                student_id,
                rng.choice(FIRST_NAMES),
                rng.choice(LAST_NAMES),
                department_id,
                enrollment_year,
                status,
            )
        )
        student_profiles.append((student_id, department_id, ability))

    course_rows = [
        (course_id, name, department_id, credits)
        for course_id, name, department_id, credits, _ in COURSES
    ]
    course_by_id = {course[0]: course for course in COURSES}
    course_ids_by_department = {
        department_id: [course[0] for course in COURSES if course[2] == department_id]
        for department_id, _ in DEPARTMENTS
    }

    grades: list[tuple[object, ...]] = []
    grade_id = 1
    all_course_ids = [course[0] for course in COURSES]
    for student_id, department_id, ability in student_profiles:
        home_courses = rng.sample(course_ids_by_department[department_id], 4)
        elective_pool = [
            course_id
            for course_id in all_course_ids
            if course_by_id[course_id][2] != department_id
        ]
        selected_courses = home_courses + rng.sample(elective_pool, 2)
        rng.shuffle(selected_courses)

        for position, course_id in enumerate(selected_courses):
            semester = "Fall" if position < 3 else "Spring"
            semester_effect = -0.5 if semester == "Fall" else 1.0
            course_difficulty = course_by_id[course_id][4]
            base = (
                ability
                + DEPARTMENT_EFFECT[department_id]
                - course_difficulty
                + semester_effect
            )
            midterm = clipped_score(base + rng.gauss(-1.5, 8.5))
            final_exam = clipped_score(base + rng.gauss(1.0, 9.0))
            grades.append(
                (
                    grade_id,
                    student_id,
                    course_id,
                    "2024-2025",
                    semester,
                    f"{midterm:.2f}",
                    f"{final_exam:.2f}",
                )
            )
            grade_id += 1

    assert len(students) == STUDENT_COUNT
    assert len(course_rows) == 40
    assert len(grades) == STUDENT_COUNT * GRADES_PER_STUDENT
    assert all(
        0 <= float(row[-2]) <= 100 and 0 <= float(row[-1]) <= 100
        for row in grades
    )
    return students, course_rows, grades


def write_seed_files(output_dir: Path) -> None:
    students, courses, grades = build_rows()

    postgres_sql = "-- Generated by generate_data.py; do not edit manually.\n"
    postgres_sql += f"-- Fixed seed: {SEED}\n\nBEGIN;\n\n"
    postgres_sql += insert_statements(
        "departments", ("department_id", "department_name"), DEPARTMENTS
    )
    postgres_sql += "\n\n"
    postgres_sql += insert_statements(
        "students",
        (
            "student_id",
            "first_name",
            "last_name",
            "department_id",
            "enrollment_year",
            "status",
        ),
        students,
    )
    postgres_sql += "\n\nCOMMIT;\n"

    mysql_sql = "-- Generated by generate_data.py; do not edit manually.\n"
    mysql_sql += f"-- Fixed seed: {SEED}\n\nSTART TRANSACTION;\n\n"
    mysql_sql += insert_statements(
        "courses",
        ("course_id", "course_name", "department_id", "credits"),
        courses,
    )
    mysql_sql += "\n\n"
    mysql_sql += insert_statements(
        "grades",
        (
            "grade_id",
            "student_id",
            "course_id",
            "academic_year",
            "semester",
            "midterm_score",
            "final_exam_score",
        ),
        grades,
    )
    mysql_sql += "\n\nCOMMIT;\n"

    output_dir.mkdir(parents=True, exist_ok=True)
    (output_dir / "postgres_seed.sql").write_text(postgres_sql, encoding="utf-8")
    (output_dir / "mysql_seed.sql").write_text(mysql_sql, encoding="utf-8")

    print(f"Generated {len(DEPARTMENTS)} departments")
    print(f"Generated {len(students)} students")
    print(f"Generated {len(courses)} courses")
    print(f"Generated {len(grades)} grades")


def main() -> None:
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument(
        "--output-dir",
        type=Path,
        default=Path(__file__).resolve().parent,
        help="Directory for postgres_seed.sql and mysql_seed.sql",
    )
    args = parser.parse_args()
    write_seed_files(args.output_dir)


if __name__ == "__main__":
    main()
