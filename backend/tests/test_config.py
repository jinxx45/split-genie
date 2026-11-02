"""Which database URL the app picks up."""

from app.config import Settings


def test_the_direct_neon_url_is_preferred(monkeypatch):
    monkeypatch.setenv("DATABASE_URL", "postgresql://pooled")
    monkeypatch.setenv("DATABASE_URL_UNPOOLED", "postgresql://direct")

    assert Settings(_env_file=None).database_url == "postgresql://direct"


def test_a_plain_database_url_works_too(monkeypatch):
    monkeypatch.delenv("DATABASE_URL_UNPOOLED", raising=False)
    monkeypatch.setenv("DATABASE_URL", "postgresql://render")

    assert Settings(_env_file=None).database_url == "postgresql://render"


def test_neons_env_file_in_the_repo_root_is_read(tmp_path, monkeypatch):
    for name in ("DATABASE_URL", "DATABASE_URL_UNPOOLED"):
        monkeypatch.delenv(name, raising=False)
    (tmp_path / "backend").mkdir()
    (tmp_path / ".env.local").write_text("DATABASE_URL=postgresql://pooled\nDATABASE_URL_UNPOOLED=postgresql://direct\n")
    monkeypatch.chdir(tmp_path / "backend")  # the backend runs from backend/

    assert Settings().database_url == "postgresql://direct"
