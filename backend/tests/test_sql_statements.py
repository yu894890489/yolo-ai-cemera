"""TDD for app.db.sql_statements: parsing .sql files into executable statements."""

from app.db.sql_statements import split_sql_statements


def test_splits_multiple_statements():
    text = "CREATE TABLE a (id INT);\nCREATE TABLE b (id INT);"
    assert split_sql_statements(text) == [
        "CREATE TABLE a (id INT)",
        "CREATE TABLE b (id INT)",
    ]


def test_strips_line_comments():
    text = (
        "-- this is a comment\n"
        "CREATE TABLE a (id INT);\n"
        "-- INSERT INTO a VALUES (1);\n"
    )
    assert split_sql_statements(text) == ["CREATE TABLE a (id INT)"]


def test_keeps_inline_dashes_inside_statement_values():
    # A dash that is not at the start of a line is part of the statement.
    text = "INSERT INTO a (note) VALUES ('multi-word-note');"
    assert split_sql_statements(text) == ["INSERT INTO a (note) VALUES ('multi-word-note')"]


def test_ignores_trailing_whitespace_and_blank_statements():
    text = "CREATE TABLE a (id INT);\n\n   \n;"
    assert split_sql_statements(text) == ["CREATE TABLE a (id INT)"]


def test_empty_input_returns_empty_list():
    assert split_sql_statements("") == []
    assert split_sql_statements("-- only a comment\n") == []
