from app.db.urls import make_sync_url


def test_make_sync_url_selects_the_installed_psycopg2_driver():
    async_url = "postgresql+asyncpg://user:pass@localhost/scanforge?channel_binding=require&sslmode=require"

    assert make_sync_url(async_url) == "postgresql+psycopg2://user:pass@localhost/scanforge?sslmode=require"


def test_make_sync_url_preserves_repeated_query_parameters_and_plain_postgresql_scheme():
    sync_url = "postgresql://user:pass@localhost/scanforge?options=one&options=two&channel_binding=require"

    assert make_sync_url(sync_url) == "postgresql+psycopg2://user:pass@localhost/scanforge?options=one&options=two"
