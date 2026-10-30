"""Testes de src/utils/db.py: credenciais, engine e disponibilidade."""

import pytest

from src.utils import db

CREDS = {"host": "h.neon.tech", "username": "u", "password": "s", "database": "d"}


@pytest.fixture(autouse=True)
def isolar(monkeypatch):
    db._ENGINE_CACHE.clear()
    for var in ("POSTGRES_HOST", "POSTGRES_DB", "POSTGRES_USER", "POSTGRES_PASSWORD"):
        monkeypatch.delenv(var, raising=False)
    monkeypatch.setattr(db, "_from_streamlit_secrets", lambda: {})
    monkeypatch.setattr(db, "_from_secrets_file", lambda: {})
    yield
    db._ENGINE_CACHE.clear()


def test_sem_credenciais_nao_levanta_e_fica_indisponivel():
    assert db.get_engine() is None
    assert db.is_available() is False


def test_senha_com_caracteres_especiais_preservada(monkeypatch):
    senha = "p@ss:w/rd#1"
    monkeypatch.setattr(db, "_from_streamlit_secrets", lambda: {**CREDS, "password": senha})
    engine = db.get_engine()
    assert engine is not None
    assert engine.url.password == senha
    assert engine.url.host == "h.neon.tech"


def test_engine_reaproveitado(monkeypatch):
    monkeypatch.setattr(db, "_from_streamlit_secrets", lambda: dict(CREDS))
    assert db.get_engine() is db.get_engine()


def test_credenciais_via_env(monkeypatch):
    monkeypatch.setenv("POSTGRES_HOST", "h.neon.tech")
    monkeypatch.setenv("POSTGRES_DB", "d")
    monkeypatch.setenv("POSTGRES_USER", "u")
    monkeypatch.setenv("POSTGRES_PASSWORD", "s")
    assert db.get_engine() is not None


def test_credenciais_incompletas_ignoradas(monkeypatch):
    monkeypatch.setattr(db, "_from_streamlit_secrets", lambda: {"host": "h"})
    assert db.get_engine() is None