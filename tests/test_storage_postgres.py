"""Tests for the PostgreSQL storage backend.

All database calls are mocked since we don't have a real PostgreSQL instance.
"""

from unittest.mock import MagicMock, patch

import pytest

from axiom_corpus.models import Subsection

try:
    from axiom_corpus.storage.postgres import POSTGRES_AVAILABLE, PostgresStorage, get_engine
    _IMPORT_OK = True
except ImportError:
    _IMPORT_OK = False
    POSTGRES_AVAILABLE = False

pytestmark = pytest.mark.skipif(not _IMPORT_OK, reason="PostgreSQL storage not importable")


class TestGetEngine:
    @pytest.mark.skipif(not POSTGRES_AVAILABLE, reason="SQLAlchemy not installed")
    def test_no_url_raises(self):
        with patch.dict("os.environ", {}, clear=True):
            with pytest.raises(ValueError, match="No database URL"):
                get_engine()

    @pytest.mark.skipif(not POSTGRES_AVAILABLE, reason="SQLAlchemy not installed")
    @patch("axiom_corpus.storage.postgres.create_engine")
    def test_url_from_param(self, mock_create):
        get_engine("postgresql://localhost/test")
        mock_create.assert_called_once()
        url = mock_create.call_args.args[0]
        assert url.render_as_string() == "postgresql+psycopg2://localhost/test"

    @pytest.mark.skipif(not POSTGRES_AVAILABLE, reason="SQLAlchemy not installed")
    @patch("axiom_corpus.storage.postgres.create_engine")
    def test_url_from_env(self, mock_create):
        with patch.dict("os.environ", {"DATABASE_URL": "postgresql://localhost/test"}):
            get_engine()
            mock_create.assert_called_once()
            url = mock_create.call_args.args[0]
            assert url.render_as_string() == "postgresql+psycopg2://localhost/test"

    @pytest.mark.skipif(not POSTGRES_AVAILABLE, reason="SQLAlchemy not installed")
    @patch("axiom_corpus.storage.postgres.create_engine")
    def test_explicit_driver_is_kept(self, mock_create):
        get_engine("postgresql+psycopg://u:pw@localhost:5432/test")
        url = mock_create.call_args.args[0]
        assert url.drivername == "postgresql+psycopg"
        assert url.password == "pw"

    @pytest.mark.skipif(not POSTGRES_AVAILABLE, reason="SQLAlchemy not installed")
    def test_bare_url_resolves_to_psycopg2(self):
        # SQLAlchemy 2.1 resolves a bare postgresql:// URL to psycopg (v3); the
        # postgres extra installs psycopg2, so get_engine names it explicitly.
        pytest.importorskip("psycopg2")
        engine = get_engine("postgresql://u:pw@localhost:5432/test")
        assert engine.dialect.driver == "psycopg2"
        assert engine.url.password == "pw"


class TestPostgresStorageSubsectionConversion:
    @pytest.mark.skipif(not POSTGRES_AVAILABLE, reason="SQLAlchemy not installed")
    def test_subsection_to_dict(self):
        storage = MagicMock(spec=PostgresStorage)
        sub = Subsection(
            identifier="a",
            heading="General rule",
            text="Tax is imposed.",
            children=[
                Subsection(identifier="1", text="Rate is 5%."),
            ],
        )
        result = PostgresStorage._subsection_to_dict(storage, sub)
        assert result["identifier"] == "a"
        assert result["heading"] == "General rule"
        assert len(result["children"]) == 1

    @pytest.mark.skipif(not POSTGRES_AVAILABLE, reason="SQLAlchemy not installed")
    def test_dict_to_subsection(self):
        storage = MagicMock(spec=PostgresStorage)
        d = {
            "identifier": "a",
            "heading": "General rule",
            "text": "Tax is imposed.",
            "children": [
                {"identifier": "1", "text": "Rate is 5%.", "children": []},
            ],
        }
        result = PostgresStorage._dict_to_subsection(storage, d)
        assert isinstance(result, Subsection)
        assert result.identifier == "a"
        assert len(result.children) == 1
