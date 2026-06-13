from db_layer.pg_adapter import PgAdapter


def test_sqlite_compat_converts_numeric_glob_to_postgres_regex():
    sql = """
        SELECT CAST(tweet_id AS INTEGER)
        FROM tweet_performance
        WHERE collection_tier = $1 AND tweet_id GLOB '[0-9]*'
    """

    converted = PgAdapter._sqlite_compat(sql)

    assert "tweet_id GLOB '[0-9]*'" not in converted
    assert "tweet_id ~ '^[0-9]+$'" in converted


def test_sqlite_compat_preserves_non_glob_sql():
    sql = "SELECT * FROM tweets WHERE id = $1"
    converted = PgAdapter._sqlite_compat(sql)
    assert converted == sql


def test_sqlite_compat_converts_multiple_globs():
    sql = "SELECT * FROM t WHERE a GLOB '[a-z]*' AND b GLOB '[0-9]*'"
    converted = PgAdapter._sqlite_compat(sql)
    assert "^[0-9]+$" in converted


def test_sqlite_compat_handles_empty_glob():
    sql = "SELECT * FROM t WHERE x GLOB ''"
    converted = PgAdapter._sqlite_compat(sql)
    assert converted == sql
