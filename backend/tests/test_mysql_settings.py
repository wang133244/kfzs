from app.config import Settings


def test_local_default_stays_sqlite():
    settings = Settings(
        mysql_address="",
        mysql_username="",
        mysql_password="",
        database_url="sqlite+aiosqlite:///./doudian.db",
    )
    assert settings.resolved_database_url.startswith("sqlite")
    assert settings.is_sqlite is True


def test_mysql_env_builds_urlencoded_connection():
    settings = Settings(
        mysql_address="10.31.107.132:3306",
        mysql_username="root",
        mysql_password="p@ss/word",
        mysql_database="doudian",
        database_url="sqlite+aiosqlite:///./doudian.db",
    )
    url = settings.resolved_database_url
    assert url.startswith("mysql+aiomysql://")
    assert "root:" in url
    assert "p%40ss%2Fword" in url
    assert "@10.31.107.132:3306/doudian" in url
    assert "charset=utf8mb4" in url
    assert settings.is_sqlite is False
    assert settings.mysql_database_name == "doudian"


def test_explicit_mysql_database_url_still_works():
    settings = Settings(
        mysql_address="",
        database_url="mysql+aiomysql://root:secret@10.0.0.1:3306/shop",
    )
    assert settings.resolved_database_url.startswith("mysql+aiomysql://root:secret@")
    assert settings.is_sqlite is False
    assert settings.mysql_database_name == "shop"


def test_mysql_admin_url_does_not_keep_app_database():
    from app.db import mysql_admin_url

    url = mysql_admin_url(
        "mysql+aiomysql://root:secret@10.31.107.132:3306/doudian?charset=utf8mb4"
    )
    assert url.database == "mysql"
    rendered = url.render_as_string(hide_password=True)
    assert "/mysql" in rendered
    assert "/doudian" not in rendered


def test_mysql_do_ping_passes_reconnect_argument():
    from app.db import mysql_do_ping

    class NeedsReconnect:
        def ping(self, reconnect):
            self.reconnect = reconnect

    conn = NeedsReconnect()
    assert mysql_do_ping(conn) is True
    assert conn.reconnect is False
