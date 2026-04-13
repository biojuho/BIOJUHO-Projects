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
