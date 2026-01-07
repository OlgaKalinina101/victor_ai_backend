from infrastructure.database.url_utils import normalize_database_url


def test_normalize_database_url_keeps_normal_url_unchanged():
    url = "postgresql+psycopg2://postgres:up2wAzqr2@localhost:5432/victor_db"
    assert normalize_database_url(url) == url


def test_normalize_database_url_escapes_broken_percent_sequences_in_password():
    # '%C2' — неполная UTF-8 последовательность (0xC2 должен иметь continuation byte),
    # из-за чего psycopg2.connect падает с UnicodeDecodeError.
    bad = "postgresql+psycopg2://user:pass%C2@localhost:5432/db"
    fixed = normalize_database_url(bad)

    # '%' должен стать literal, то есть быть экранирован как %25
    assert "pass%25C2" in fixed
    assert fixed.startswith("postgresql+psycopg2://user:")
    assert fixed.endswith("@localhost:5432/db")


