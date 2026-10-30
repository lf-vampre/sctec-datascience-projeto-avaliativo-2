"""Gerenciamento de conexão resiliente com o banco PostgreSQL (Neon)."""

import os
import tomllib
from typing import Any, Dict, Optional, Tuple

from sqlalchemy import Engine, create_engine, text
from sqlalchemy.engine import URL

from src.utils.paths import ROOT_DIR

_CAMPOS_OBRIGATORIOS = ("host", "username", "password", "database")
_ENGINE_CACHE: Dict[Tuple, Engine] = {}


def _from_streamlit_secrets() -> Dict[str, Any]:
    """Lê [connections.postgresql] de st.secrets (Streamlit Cloud). Import tardio e tolerante."""
    try:
        import streamlit as st

        return dict(st.secrets["connections"]["postgresql"])
    except Exception:
        return {}


def _from_secrets_file() -> Dict[str, Any]:
    """Lê [connections.postgresql] do .streamlit/secrets.toml local."""
    secrets_path = ROOT_DIR / ".streamlit" / "secrets.toml"
    if not secrets_path.exists():
        return {}
    try:
        with open(secrets_path, "rb") as f:
            return dict(tomllib.load(f).get("connections", {}).get("postgresql", {}))
    except Exception:
        return {}


def _from_env() -> Dict[str, Any]:
    """Lê credenciais das variáveis de ambiente POSTGRES_*."""
    return {
        "dialect": os.getenv("POSTGRES_DIALECT", "postgresql"),
        "host": os.getenv("POSTGRES_HOST"),
        "port": os.getenv("POSTGRES_PORT", "5432"),
        "database": os.getenv("POSTGRES_DB"),
        "username": os.getenv("POSTGRES_USER"),
        "password": os.getenv("POSTGRES_PASSWORD"),
        "sslmode": os.getenv("POSTGRES_SSLMODE", "require"),
    }


def _completo(creds: Dict[str, Any]) -> bool:
    return all(creds.get(k) for k in _CAMPOS_OBRIGATORIOS)


def _load_db_credentials() -> Dict[str, Any]:
    """Credenciais na ordem: st.secrets (Cloud) → secrets.toml (local) → variáveis de ambiente."""
    for fonte in (_from_streamlit_secrets, _from_secrets_file):
        creds = fonte()
        if _completo(creds):
            return creds
    return _from_env()


def get_engine() -> Optional[Engine]:
    """Retorna o Engine SQLAlchemy (reaproveitado), com pool_pre_ping e timeout curto."""
    creds = _load_db_credentials()
    if not _completo(creds):
        return None

    dialect = creds.get("dialect") or "postgresql"
    sslmode = creds.get("sslmode") or "require"
    key = (
        dialect, creds["username"], creds["password"],
        creds["host"], str(creds.get("port") or 5432), creds["database"], sslmode,
    )

    engine = _ENGINE_CACHE.get(key)
    if engine is not None:
        return engine

    try:
        url = URL.create(
            drivername=dialect,
            username=creds["username"],
            password=creds["password"],
            host=creds["host"],
            port=int(creds.get("port") or 5432),
            database=creds["database"],
            query={"sslmode": sslmode},
        )
        engine = create_engine(url, pool_pre_ping=True, connect_args={"connect_timeout": 5})
    except Exception:
        return None

    for antigo in _ENGINE_CACHE.values():
        antigo.dispose()
    _ENGINE_CACHE.clear()
    _ENGINE_CACHE[key] = engine
    return engine


def is_available() -> bool:
    """Testa a disponibilidade da conexão com o banco. Retorna bool e nunca lança exceção."""
    try:
        engine = get_engine()
        if engine is None:
            return False
        with engine.connect() as conn:
            conn.execute(text("SELECT 1"))
        return True
    except Exception:
        return False